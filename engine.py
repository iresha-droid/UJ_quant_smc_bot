from __future__ import annotations

import importlib.util
import hashlib
import json
import math
from itertools import chain
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from config import BacktestConfig
from data_loader import HistoricalDataLoader, HistoricalNewsLoader
from order_simulator import OrderSimulator
from performance import PerformanceEngine
from progress import BacktestProgressCheckpoint, BacktestRunPersistence
from synchronizer import TimeframeSynchronizer
from tick_loader import HistoricalTickLoader
from trade_journal import TradeJournal, TradeRecord
from trade_manager import TradeManager
from validation import BacktestAudit, BacktestValidator


@dataclass
class SignalEvent:
    ts: pd.Timestamp
    m5_index: int
    decision: str
    long_score: float
    short_score: float
    context: Dict[str, Any] = field(default_factory=dict)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TradeExecutionResult:
    ticket: int
    direction: str
    entry: float
    sl: float
    tp: float
    exit_price: float
    exit_reason: str
    pnl: float
    status: str
    open_time: str
    close_time: str


class HistoricalBacktestEngine:
    """External historical backtest engine built around the existing production
    signal logic without editing the production file.
    """

    def __init__(self, project_root: Optional[Path] = None, config: Optional[BacktestConfig] = None):
        self.project_root = project_root or Path(__file__).resolve().parents[1]
        self.config = config or BacktestConfig(project_root=self.project_root)
        self.loader = HistoricalDataLoader(project_root=self.project_root, use_b2=False)
        self.news_loader = HistoricalNewsLoader(
            project_root=self.project_root,
            calendar_file=self.config.local_datasets.get("CALENDAR", "XAUUSD_6M_calendar.csv"),
        )
        self.b2 = None
        if self.config.use_b2:
            try:
                from b2_client import B2HistoricalDataAccess
                self.b2 = B2HistoricalDataAccess(project_root=self.project_root)
            except ImportError:
                raise ImportError("B2 support requires boto3 and b2_client to be installed")
        self.tick_loader = HistoricalTickLoader(
            project_root=self.project_root,
            tick_file=self.config.local_datasets.get("TICK", "XAUUSD_TICKS_6M.csv"),
            b2=self.b2,
        )
        self.order_sim = OrderSimulator(symbol=self.config.symbol, slippage_points=self.config.slippage_points, spread_points=self.config.spread_points)
        self.trade_manager = TradeManager(simulator=self.order_sim, config=self.config.__dict__)
        self.performance = PerformanceEngine()
        self.journal = TradeJournal(project_root=self.project_root)
        self.validator = BacktestValidator()
        self.production_module = self._load_production_module()
        self._run_tick_data: Optional[pd.DataFrame] = None
        self._run_news_data: Optional[pd.DataFrame] = None
        self._feature_cache: Dict[Tuple[str, int, pd.Timestamp], pd.DataFrame] = {}
        self._m5_features: Optional[pd.DataFrame] = None

    def _load_production_module(self):
        path = self.project_root / 'engine_before_backtest.py'
        if not path.exists():
            raise FileNotFoundError(
                f"Backtest strategy module is missing: {path}. "
                "Expected engine_before_backtest.py, which must be an exact copy "
                "of the original production strategy."
            )
        spec = importlib.util.spec_from_file_location('prod_main_ext', path)
        if spec is None or spec.loader is None:
            raise ImportError(f'Unable to load production module from {path}')
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def _load_historical_data(self, start_date: Optional[str] = None, end_date: Optional[str] = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        m5 = self.loader.load_timeframe('M5', self.config.symbol, start_date, end_date)
        h1 = self.loader.load_timeframe('H1', self.config.symbol, start_date, end_date)
        h4 = self.loader.load_timeframe('H4', self.config.symbol, start_date, end_date)
        return h4.sort_values('timestamp').reset_index(drop=True), h1.sort_values('timestamp').reset_index(drop=True), m5.sort_values('timestamp').reset_index(drop=True)

    def _select_window(self, m5_df: pd.DataFrame, window: Optional[int] = None) -> pd.DataFrame:
        if window is not None and window > 0:
            return m5_df.tail(window).copy().reset_index(drop=True)
        return m5_df.copy().reset_index(drop=True)

    def _sync_context(self, h4_df: pd.DataFrame, h1_df: pd.DataFrame, m5_df: pd.DataFrame, idx: int) -> Dict[str, Any]:
        sync = TimeframeSynchronizer(h4_df, h1_df, m5_df)
        ctx = sync(idx)
        return {
            'ts': ctx.ts,
            'm5': ctx.m5,
            'h1': ctx.h1,
            'h4': ctx.h4,
        }

    def _build_features_cached(self, timeframe: str, frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return pd.DataFrame()
        key = (timeframe, len(frame), pd.Timestamp(frame['timestamp'].iloc[-1]))
        cached = self._feature_cache.get(key)
        if cached is None:
            cached = self.production_module.build_smc_features(frame.copy())
            self._feature_cache[key] = cached
        return cached.copy()

    def _prepare_m5_features(self, m5_df: pd.DataFrame) -> None:
        self._m5_features = self.production_module.build_smc_features(m5_df.copy())

    def _m5_features_for_prefix(self, prefix: pd.DataFrame, idx: int) -> pd.DataFrame:
        if self._m5_features is None:
            return self.production_module.build_smc_features(prefix.copy())
        features = prefix.copy()
        full_row = self._m5_features.iloc[idx]
        for column in self._m5_features.columns:
            if column not in prefix.columns and column not in {'swing_high', 'swing_low'}:
                features[column] = full_row[column]
        return features

    def _replay_session(self, timestamp: pd.Timestamp) -> str:
        detect_session = getattr(self.production_module, 'detect_session', None)
        if detect_session is not None:
            return str(detect_session(pd.Timestamp(timestamp).to_pydatetime()).value)
        return 'REPLAY'

    def _news_blocked_at(self, timestamp: pd.Timestamp) -> bool:
        if not getattr(self.config, 'news_protection', True) or self._run_news_data is None:
            return False
        pre_minutes = float(getattr(self.production_module.settings, 'PRE_NEWS_MINUTES', 30))
        freeze_minutes = float(getattr(self.production_module.settings, 'NEWS_FREEZE_MINUTES', 20))
        current = pd.Timestamp(timestamp)
        for event_time in self._run_news_data['timestamp']:
            delta_minutes = (pd.Timestamp(event_time) - current).total_seconds() / 60.0
            if -freeze_minutes <= delta_minutes <= pre_minutes:
                return True
        return False

    def _checkpoint_runtime_state(self, progress: Dict[str, Any]) -> None:
        progress['simulator_state'] = self.order_sim.snapshot()
        progress['trade_manager_state'] = self.trade_manager.snapshot()

    def _sync_trading_mode(self) -> Tuple[str, int]:
        """Drive production mode switching from the current simulated balance."""
        self.production_module.state.balance = self.trade_manager.balance
        self.production_module.update_trading_mode()
        mode = self.production_module.state.mode
        max_positions = int(self.production_module.get_max_open_positions())
        return mode, max_positions

    def _plan_for_signal(self, signal: 'SignalEvent', mode: str) -> Tuple[float, float, Any]:
        """Build entry, sl/tp and a validated trade plan exactly like production."""
        entry = float(signal.context['m5']['Close'].iloc[-1])
        sl, tp = self.production_module.calculate_sl_tp(signal.decision, entry, signal.context['m5'], signal.context['h1'])
        if mode == "SINGLE_TRADE":
            tp = 0.0
        plan = self.production_module.validate_trade(
            signal.decision, entry, sl, tp, self.trade_manager.balance, self.config.symbol,
            allow_no_tp=(mode == "SINGLE_TRADE"),
        )
        if plan.valid:
            regime = self.production_module.check_market_regime(signal.context['m5'])
            multiplier = float(regime.get('size_multiplier', 1.0))
            if multiplier < 1.0:
                specs = self.production_module.get_symbol_specs(self.config.symbol)
                step = max(float(specs['lot_step']), 1e-8)
                reduced = plan.position_size * multiplier
                plan.position_size = math.floor(reduced / step) * step
                if plan.position_size <= 0:
                    plan.valid = False
                    plan.reason = 'REGIME_SIZE_REDUCTION'
            if plan.valid and mode == "SINGLE_TRADE":
                plan.tp = 0.0
        return sl, tp, plan

    def _resume_fingerprint(self, h4_df: pd.DataFrame, h1_df: pd.DataFrame, m5_df: pd.DataFrame, start_date: Optional[str], end_date: Optional[str], window: Optional[int], use_ticks: bool) -> str:
        def file_identity(path: Path, logical_name: str) -> Dict[str, Any]:
            resolved = path.resolve()
            if not resolved.exists():
                return {'name': logical_name, 'missing': True}
            digest = hashlib.sha256()
            with resolved.open('rb') as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b''):
                    digest.update(chunk)
            return {'name': logical_name, 'size': resolved.stat().st_size, 'sha256': digest.hexdigest()}

        def frame_identity(frame: pd.DataFrame) -> Dict[str, Any]:
            return {'rows': len(frame), 'start': str(frame['timestamp'].min()) if not frame.empty else None, 'end': str(frame['timestamp'].max()) if not frame.empty else None}

        config = {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(self.config).items()
            if key != 'project_root'
        }
        tick_paths = getattr(self.tick_loader, "source_paths", lambda *_args: [self.tick_loader.path()])(start_date, end_date)
        payload = {
            'config': config,
            'requested_period': {'start': start_date, 'end': end_date, 'window': window},
            'use_ticks': use_ticks,
            'strategy_sha256': hashlib.sha256((self.project_root / 'engine_before_backtest.py').read_bytes()).hexdigest(),
            'datasets': {
                'm5': file_identity(self.project_root / 'XAUUSD_M5_6M.csv', 'XAUUSD_M5_6M.csv'),
                'h1': file_identity(self.project_root / 'XAUUSD_H1_6M.csv', 'XAUUSD_H1_6M.csv'),
                'h4': file_identity(self.project_root / 'XAUUSD_H4_6M.csv', 'XAUUSD_H4_6M.csv'),
                'calendar': file_identity(self.project_root / self.news_loader.calendar_file, self.news_loader.calendar_file),
                'tick': [file_identity(path, path.name) for path in tick_paths],
            },
            'loaded_frames': {'m5': frame_identity(m5_df), 'h1': frame_identity(h1_df), 'h4': frame_identity(h4_df)},
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _validate_signal_state(state: Any) -> None:
        required_counters = {'valid_4h_context', 'valid_1h_setup', 'valid_5m_trigger', 'buy', 'sell', 'no_trade', 'warmup_skipped', 'lookahead_violations'}
        if not isinstance(state, dict) or not isinstance(state.get('counters'), dict) or required_counters - state['counters'].keys():
            raise ValueError('Checkpoint signal state is incomplete')
        if not isinstance(state.get('warnings'), list) or not isinstance(state.get('reasons'), list) or not isinstance(state.get('signals_generated'), int):
            raise ValueError('Checkpoint signal state is malformed')

    @staticmethod
    def _validate_simulator_state(state: Any) -> None:
        if not isinstance(state, dict):
            raise ValueError('Checkpoint lacks complete simulator state; refusing unsafe resume')
        if not isinstance(state.get('next_ticket'), int):
            raise ValueError('Simulator checkpoint state is malformed')
        for key in ('open_positions', 'closed_positions'):
            if not isinstance(state.get(key), list):
                raise ValueError('Simulator checkpoint state is malformed')
            for trade in state[key]:
                if not isinstance(trade, dict) or {
                    'symbol', 'direction', 'entry', 'sl', 'tp', 'lot_size', 'ticket',
                    'magic', 'open_time', 'initial_risk', 'pnl', 'exit_time',
                    'exit_reason', 'closed', 'session', 'score_info',
                } - trade.keys():
                    raise ValueError('Simulator checkpoint state is malformed')

    @staticmethod
    def _serialize_active_tick_replay(active: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            'active_positions': [
                {
                    'ticket': item['trade'].ticket,
                    'm5_index': item['signal'].m5_index,
                    'direction': item['signal'].decision,
                    'signal_timestamp': str(item['signal'].ts),
                    'long_score': item['signal'].long_score,
                    'short_score': item['signal'].short_score,
                    'details': item['signal'].details,
                    'raw_entry': item['raw_entry'],
                    'sl': item['sl'],
                    'tp': item['tp'],
                    'trade_end': str(item['trade_end']),
                    'last_price': item['last_price'],
                    'last_timestamp': str(item['last_timestamp']),
                    'tick_count': item['tick_count'],
                    'initial_risk': item['initial_risk'],
                    'highest_r': item['highest_r'],
                    'breakeven': item['breakeven'],
                    'news_protected': item['news_protected'],
                }
                for item in active
            ]
        }

    def _restore_active_tick_replay(self, state: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not isinstance(state, dict) or not isinstance(state.get('active_positions'), list):
            raise ValueError('Tick replay checkpoint state is malformed')
        active: List[Dict[str, Any]] = []
        try:
            for record in state['active_positions']:
                ticket = int(record['ticket'])
                trade = self.order_sim.open_positions[ticket]
                signal = SignalEvent(
                    ts=pd.Timestamp(record['signal_timestamp']),
                    m5_index=int(record['m5_index']),
                    decision=str(record['direction']),
                    long_score=float(record['long_score']),
                    short_score=float(record['short_score']),
                    details=dict(record['details']),
                )
                active.append({
                    'signal': signal,
                    'trade': trade,
                    'raw_entry': float(record['raw_entry']),
                    'sl': float(record['sl']),
                    'tp': float(record['tp']),
                    'trade_end': pd.Timestamp(record['trade_end']),
                    'last_price': float(record['last_price']),
                    'last_timestamp': pd.Timestamp(record['last_timestamp']),
                    'tick_count': int(record['tick_count']),
                    'initial_risk': float(record.get('initial_risk', abs(float(record['raw_entry']) - float(record['sl'])) or 1e-8)),
                    'highest_r': float(record.get('highest_r', 0.0)),
                    'breakeven': bool(record.get('breakeven', False)),
                    'news_protected': bool(record.get('news_protected', False)),
                })
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Tick replay checkpoint state is malformed') from error
        return active

    @staticmethod
    def _validate_tick_replay_state(state: Any) -> None:
        if not isinstance(state, dict) or not isinstance(state.get('active_positions'), list):
            raise ValueError('Tick replay checkpoint state is malformed')
        cursor = state.get('tick_cursor')
        if cursor is None:
            return
        if not isinstance(cursor, dict) or {
            'stream_start', 'stream_end', 'processed_tick_count'
        } - cursor.keys():
            raise ValueError('Tick replay checkpoint cursor is malformed')
        if not isinstance(cursor['stream_start'], str) or not isinstance(cursor['stream_end'], str):
            raise ValueError('Tick replay checkpoint cursor is malformed')
        try:
            stream_start = pd.Timestamp(cursor['stream_start'])
            stream_end = pd.Timestamp(cursor['stream_end'])
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError('Tick replay checkpoint cursor is malformed') from error
        processed_tick_count = cursor['processed_tick_count']
        if (
            pd.isna(stream_start)
            or pd.isna(stream_end)
            or stream_end < stream_start
            or type(processed_tick_count) is not int
            or processed_tick_count < 0
        ):
            raise ValueError('Tick replay checkpoint cursor is malformed')

    def _manage_active_positions(self, active: List[Dict[str, Any]], trades: List['TradeExecutionResult'], signal: 'SignalEvent') -> None:
        """Reproduce production's per-candle-close runner management (no lookahead: uses only the causal m5/h4 context of the just-closed candle)."""
        m5_ctx = signal.context.get('m5', pd.DataFrame())
        h4_ctx = signal.context.get('h4', pd.DataFrame())
        if m5_ctx.empty or not active:
            return
        current_price = float(m5_ctx['Close'].iloc[-1])
        remaining: List[Dict[str, Any]] = []
        for item in active:
            direction = item['signal'].decision
            initial_risk = item['initial_risk'] or 1e-8
            current_r = (current_price - item['raw_entry']) / initial_risk if direction == 'BUY' else (item['raw_entry'] - current_price) / initial_risk
            item['highest_r'] = max(item['highest_r'], current_r)

            if not h4_ctx.empty:
                structure, _ = self.production_module.detect_bos_choch(h4_ctx)
                Structure = self.production_module.Structure
                broke = (direction == 'BUY' and structure == Structure.BEARISH_CHOCH) or (direction == 'SELL' and structure == Structure.BULLISH_CHOCH)
                if broke:
                    closed = self.order_sim.close_position(item['trade'].ticket, current_price, 'HTF_STRUCTURE_BREAK')
                    self.trade_manager.record_exit(closed)
                    trades.append(TradeExecutionResult(
                        item['trade'].ticket, direction, item['raw_entry'], item['sl'], item['tp'],
                        current_price, 'HTF_STRUCTURE_BREAK',
                        current_price - item['raw_entry'] if direction == 'BUY' else item['raw_entry'] - current_price,
                        'CLOSED', str(item['signal'].ts), str(signal.ts),
                    ))
                    continue

            if self._news_blocked_at(signal.ts) and not item['news_protected'] and item['highest_r'] < 2.0:
                atr = self.production_module._get_atr(m5_ctx)
                buffer = atr * 0.5 if atr > 0 else (0.15 if self.config.symbol == 'XAUUSD' else 1.5)
                item['sl'] = item['raw_entry'] - buffer if direction == 'BUY' else item['raw_entry'] + buffer
                item['news_protected'] = True

            if not item['breakeven'] and current_r >= 1.0:
                item['sl'] = item['raw_entry']
                item['breakeven'] = True

            new_sl, changed = self.production_module.calculate_trailing_sl(direction, item['sl'], item['raw_entry'], m5_ctx, current_r)
            if changed:
                item['sl'] = new_sl

            remaining.append(item)
        active[:] = remaining

    def _signals_for_window(self, h4_df: pd.DataFrame, h1_df: pd.DataFrame, m5_df: pd.DataFrame, checkpoint: Optional[BacktestProgressCheckpoint] = None, progress: Optional[Dict[str, Any]] = None, start_idx: int = 0, state: Optional[Dict[str, Any]] = None):
        default_counters = {
            'valid_4h_context': 0,
            'valid_1h_setup': 0,
            'valid_5m_trigger': 0,
            'buy': 0,
            'sell': 0,
            'no_trade': 0,
            'warmup_skipped': 0,
            'lookahead_violations': 0,
        }
        if state and state.get('counters') is not None:
            self._validate_signal_state(state)
            counters, warnings, reasons, signals_generated = state['counters'], state['warnings'], state['reasons'], state['signals_generated']
        else:
            counters = default_counters
            warnings: List[str] = []
            reasons: List[str] = []
            signals_generated = 0
            if state is not None:
                state.update({'counters': counters, 'warnings': warnings, 'reasons': reasons, 'signals_generated': signals_generated})
        sync = TimeframeSynchronizer(h4_df, h1_df, m5_df)
        self._prepare_m5_features(m5_df)

        for idx in range(start_idx, len(m5_df)):
            synced = sync(idx)
            ctx = {
                'ts': synced.ts,
                'm5': synced.m5,
                'h1': synced.h1,
                'h4': synced.h4,
            }
            news_events = self.news_loader.events_at(self._run_news_data, ctx['ts']) if self._run_news_data is not None else []
            if len(ctx['m5']) < 30:
                counters['warmup_skipped'] += 1
                continue
            counters['valid_5m_trigger'] += 1
            if not ctx['h4'].empty:
                counters['valid_4h_context'] += 1
            if not ctx['h1'].empty:
                counters['valid_1h_setup'] += 1

            if not ctx['h1'].empty and ctx['h1']['timestamp'].max() > ctx['ts']:
                counters['lookahead_violations'] += 1
                warnings.append(f'lookahead_h1_at_{ctx["ts"]}')
            if not ctx['h4'].empty and ctx['h4']['timestamp'].max() > ctx['ts']:
                counters['lookahead_violations'] += 1
                warnings.append(f'lookahead_h4_at_{ctx["ts"]}')

            h4f = self._build_features_cached('H4', ctx['h4'])
            h1f = self._build_features_cached('H1', ctx['h1'])
            m5f = self._m5_features_for_prefix(ctx['m5'], idx)
            if h4f.empty or h1f.empty:
                counters['no_trade'] += 1
                reasons.append('missing_higher_tf_context')
                continue

            result = self.production_module.evaluate_entry(h4f, h1f, m5f, False)
            if hasattr(result, 'details'):
                result.details['historical_news'] = news_events
            decision = getattr(result, 'decision', 'NO SETUP')
            if decision == 'BUY':
                counters['buy'] += 1
            elif decision == 'SELL':
                counters['sell'] += 1
            else:
                counters['no_trade'] += 1
                reasons.append('no_actionable_setup')

            signals_generated += 1
            if state is not None:
                state['signals_generated'] = signals_generated
            if progress is not None:
                progress['signals_generated'] = progress.get('signals_generated', 0) + 1
                if state is not None:
                    progress['signal_state'] = state
            yield SignalEvent(
                ts=ctx['ts'],
                m5_index=idx,
                decision=decision,
                long_score=float(getattr(result, 'long_score', 0.0)),
                short_score=float(getattr(result, 'short_score', 0.0)),
                context={'h4': ctx['h4'], 'h1': ctx['h1'], 'm5': ctx['m5'], 'news': news_events},
                details=getattr(result, 'details', {}),
            )
            if checkpoint is not None and progress is not None:
                progress.update({
                    'm5_candles_processed': idx + 1,
                    'm5_candle_timestamp': str(ctx['ts']),
                    'h1_candles_loaded': len(h1_df),
                    'h4_candles_loaded': len(h4_df),
                    'signals_generated': progress.get('signals_generated', 0),
                    'trades_executed': progress.get('trades_executed', 0),
                    'ticks_processed': progress.get('ticks_processed', 0),
                    'tick_loader_calls': progress.get('tick_loader_calls', 0),
                    'current_stage': 'signal_generation',
                    'errors': progress.get('errors', []),
                    'warnings': warnings,
                    'no_lookahead_violations': counters['lookahead_violations'],
                })
                self._checkpoint_runtime_state(progress)
                checkpoint.maybe_write(idx + 1, progress)

        if progress is not None:
            progress['_signal_counters'] = counters
            progress['_signal_warnings'] = warnings
            progress['_signal_reasons'] = reasons
        if state is not None:
            state.update({
                'counters': counters,
                'warnings': warnings,
                'reasons': reasons,
                'signals_generated': signals_generated,
            })

    def _tick_execution(self, signal: SignalEvent, end_time: Optional[pd.Timestamp] = None, progress: Optional[Dict[str, Any]] = None) -> TradeExecutionResult:
        tick_loader = self._run_tick_data
        trade_end = end_time or signal.ts + pd.Timedelta(hours=1)
        if tick_loader is None:
            return TradeExecutionResult(
                ticket=0,
                direction=signal.decision,
                entry=float(signal.context['m5']['Close'].iloc[-1]),
                sl=0.0,
                tp=0.0,
                exit_price=0.0,
                exit_reason='NO_TICK_DATA',
                pnl=0.0,
                status='SKIPPED',
                open_time=str(signal.ts),
                close_time=str(signal.ts),
            )
        tick_chunks = tick_loader.iter_chunks(start_date=str(signal.ts), end_date=str(trade_end))
        first_chunk = next(tick_chunks, None)
        if first_chunk is None:
            return TradeExecutionResult(
                ticket=0,
                direction=signal.decision,
                entry=float(signal.context['m5']['Close'].iloc[-1]),
                sl=0.0,
                tp=0.0,
                exit_price=0.0,
                exit_reason='NO_TICK_DATA',
                pnl=0.0,
                status='SKIPPED',
                open_time=str(signal.ts),
                close_time=str(signal.ts),
            )

        mode, max_positions = self._sync_trading_mode()
        entry = float(signal.context['m5']['Close'].iloc[-1])
        sl, tp, plan = self._plan_for_signal(signal, mode)
        if not plan.valid:
            return TradeExecutionResult(
                ticket=0,
                direction=signal.decision,
                entry=entry,
                sl=sl,
                tp=tp,
                exit_price=entry,
                exit_reason='INVALID_PLAN',
                pnl=0.0,
                status='REJECTED',
                open_time=str(signal.ts),
                close_time=str(signal.ts),
            )
        tp = plan.tp

        session = self._replay_session(signal.ts)
        allowed, limit_reason = self.trade_manager.allow_entry(
            signal.ts,
            session,
            news_blocked=self._news_blocked_at(signal.ts),
            max_open_positions=max_positions,
        )
        if not allowed:
            return TradeExecutionResult(
                ticket=0,
                direction=signal.decision,
                entry=entry,
                sl=sl,
                tp=tp,
                exit_price=entry,
                exit_reason=limit_reason,
                pnl=0.0,
                status='REJECTED',
                open_time=str(signal.ts),
                close_time=str(signal.ts),
            )
        self.trade_manager.record_entry()
        trade = self.order_sim.create_order(signal.decision, entry, sl, tp, plan.position_size, session=session, score_info={'decision': signal.decision})
        last_price = entry
        last_timestamp = signal.ts
        tick_count = 0
        for tick_chunk in chain((first_chunk,), tick_chunks):
            for row in tick_chunk.itertuples(index=False):
                tick_count += 1
                last_timestamp = row.timestamp
                bid = float(row.bid)
                ask = float(row.ask)
                exit_price = bid if signal.decision == 'BUY' else ask
                if signal.decision == 'BUY':
                    if bid <= sl:
                        last_price = bid
                        closed = self.order_sim.close_position(trade.ticket, bid, 'STOP_OUT')
                        self.trade_manager.record_exit(closed)
                        return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, bid, 'STOP_OUT', bid - entry, 'CLOSED', str(signal.ts), str(row.timestamp))
                    if tp and exit_price >= tp:
                        last_price = exit_price
                        closed = self.order_sim.close_position(trade.ticket, exit_price, 'TARGET_HIT')
                        self.trade_manager.record_exit(closed)
                        return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, exit_price, 'TARGET_HIT', exit_price - entry, 'CLOSED', str(signal.ts), str(row.timestamp))
                else:
                    if ask >= sl:
                        last_price = ask
                        closed = self.order_sim.close_position(trade.ticket, ask, 'STOP_OUT')
                        self.trade_manager.record_exit(closed)
                        return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, ask, 'STOP_OUT', entry - ask, 'CLOSED', str(signal.ts), str(row.timestamp))
                    if tp and exit_price <= tp:
                        last_price = exit_price
                        closed = self.order_sim.close_position(trade.ticket, exit_price, 'TARGET_HIT')
                        self.trade_manager.record_exit(closed)
                        return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, exit_price, 'TARGET_HIT', entry - exit_price, 'CLOSED', str(signal.ts), str(row.timestamp))

        if progress is not None:
            progress['ticks_processed'] = progress.get('ticks_processed', 0) + tick_count
        if not tick_count:
            return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, 0.0, 'NO_TICK_DATA', 0.0, 'SKIPPED', str(signal.ts), str(signal.ts))

        # Fallback no tick hit
        closed = self.order_sim.close_position(trade.ticket, last_price, 'TIME_EXIT')
        self.trade_manager.record_exit(closed)
        return TradeExecutionResult(trade.ticket, signal.decision, entry, sl, tp, last_price, 'TIME_EXIT', last_price - entry if signal.decision == 'BUY' else entry - last_price, 'CLOSED', str(signal.ts), str(last_timestamp))

    def _chronological_tick_replay(self, signal_iter: Iterator[SignalEvent], m5_df: pd.DataFrame, progress: Dict[str, Any], checkpoint: Optional[BacktestProgressCheckpoint] = None, resume_state: Optional[Dict[str, Any]] = None) -> Tuple[List[TradeExecutionResult], int]:
        trades: List[TradeExecutionResult] = []
        active = self._restore_active_tick_replay(resume_state) if resume_state is not None else []
        execution_count = 0
        if self._run_tick_data is None:
            return trades, execution_count

        saved_cursor = (resume_state or {}).get('tick_cursor')
        if saved_cursor is not None:
            self._validate_tick_replay_state(resume_state)
            stream_start = pd.Timestamp(saved_cursor['stream_start'])
            stream_end = pd.Timestamp(saved_cursor['stream_end'])
            processed_tick_count = saved_cursor['processed_tick_count']
        else:
            first_signal = next(signal_iter, None)
            if first_signal is None:
                return trades, execution_count
            stream_start = pd.Timestamp(first_signal.ts)
            stream_end = pd.Timestamp(m5_df['timestamp'].max()) + pd.Timedelta(hours=1)
            processed_tick_count = 0
        tick_iter = self._run_tick_data.iter_chunks(
            start_date=str(stream_start),
            end_date=str(stream_end),
        )
        current_chunk = next(tick_iter, None)
        chunk_rows = iter(current_chunk.itertuples(index=False)) if current_chunk is not None else iter(())
        next_row = next(chunk_rows, None)

        for _ in range(processed_tick_count):
            if next_row is None:
                raise ValueError('Tick replay checkpoint cursor is outside the tick stream')
            next_row = next(chunk_rows, None)
            while next_row is None:
                current_chunk = next(tick_iter, None)
                if current_chunk is None:
                    raise ValueError('Tick replay checkpoint cursor is outside the tick stream')
                chunk_rows = iter(current_chunk.itertuples(index=False))
                next_row = next(chunk_rows, None)

        if saved_cursor is not None:
            first_signal = next(signal_iter, None)
            if first_signal is None:
                return trades, execution_count

        def advance_row():
            nonlocal current_chunk, chunk_rows, next_row
            next_row = next(chunk_rows, None)
            while next_row is None:
                current_chunk = next(tick_iter, None)
                if current_chunk is None:
                    return
                chunk_rows = iter(current_chunk.itertuples(index=False))
                next_row = next(chunk_rows, None)

        def finish_expired(timestamp: pd.Timestamp) -> None:
            remaining: List[Dict[str, Any]] = []
            for item in active:
                if timestamp <= item['trade_end']:
                    remaining.append(item)
                    continue
                if item['tick_count']:
                    closed = self.order_sim.close_position(item['trade'].ticket, item['last_price'], 'TIME_EXIT')
                    self.trade_manager.record_exit(closed)
                    trades.append(TradeExecutionResult(
                        item['trade'].ticket, item['signal'].decision, item['raw_entry'], item['sl'], item['tp'],
                        item['last_price'], 'TIME_EXIT',
                        item['last_price'] - item['raw_entry'] if item['signal'].decision == 'BUY' else item['raw_entry'] - item['last_price'],
                        'CLOSED', str(item['signal'].ts), str(item['last_timestamp']),
                    ))
                else:
                    self.order_sim.open_positions.pop(item['trade'].ticket, None)
                    trades.append(TradeExecutionResult(
                        item['trade'].ticket, item['signal'].decision, item['raw_entry'], item['sl'], item['tp'],
                        0.0, 'NO_TICK_DATA', 0.0, 'SKIPPED', str(item['signal'].ts), str(item['signal'].ts),
                    ))
            active[:] = remaining

        def process_until(timestamp: pd.Timestamp, inclusive: bool = True) -> None:
            nonlocal processed_tick_count
            while next_row is not None and (pd.Timestamp(next_row.timestamp) <= timestamp if inclusive else pd.Timestamp(next_row.timestamp) < timestamp):
                tick_timestamp = pd.Timestamp(next_row.timestamp)
                processed_tick_count += 1
                finish_expired(tick_timestamp)
                for item in list(active):
                    if tick_timestamp < item['signal'].ts or tick_timestamp > item['trade_end']:
                        continue
                    item['tick_count'] += 1
                    item['last_timestamp'] = tick_timestamp
                    progress['ticks_processed'] = progress.get('ticks_processed', 0) + 1
                    bid = float(next_row.bid)
                    ask = float(next_row.ask)
                    exit_price = bid if item['signal'].decision == 'BUY' else ask
                    if item['signal'].decision == 'BUY':
                        if bid <= item['sl']:
                            closed = self.order_sim.close_position(item['trade'].ticket, bid, 'STOP_OUT')
                            self.trade_manager.record_exit(closed)
                            trades.append(TradeExecutionResult(item['trade'].ticket, 'BUY', item['raw_entry'], item['sl'], item['tp'], bid, 'STOP_OUT', bid - item['raw_entry'], 'CLOSED', str(item['signal'].ts), str(tick_timestamp)))
                            active.remove(item)
                        elif item['tp'] and exit_price >= item['tp']:
                            closed = self.order_sim.close_position(item['trade'].ticket, exit_price, 'TARGET_HIT')
                            self.trade_manager.record_exit(closed)
                            trades.append(TradeExecutionResult(item['trade'].ticket, 'BUY', item['raw_entry'], item['sl'], item['tp'], exit_price, 'TARGET_HIT', exit_price - item['raw_entry'], 'CLOSED', str(item['signal'].ts), str(tick_timestamp)))
                            active.remove(item)
                    else:
                        if ask >= item['sl']:
                            closed = self.order_sim.close_position(item['trade'].ticket, ask, 'STOP_OUT')
                            self.trade_manager.record_exit(closed)
                            trades.append(TradeExecutionResult(item['trade'].ticket, 'SELL', item['raw_entry'], item['sl'], item['tp'], ask, 'STOP_OUT', item['raw_entry'] - ask, 'CLOSED', str(item['signal'].ts), str(tick_timestamp)))
                            active.remove(item)
                        elif item['tp'] and exit_price <= item['tp']:
                            closed = self.order_sim.close_position(item['trade'].ticket, exit_price, 'TARGET_HIT')
                            self.trade_manager.record_exit(closed)
                            trades.append(TradeExecutionResult(item['trade'].ticket, 'SELL', item['raw_entry'], item['sl'], item['tp'], exit_price, 'TARGET_HIT', item['raw_entry'] - exit_price, 'CLOSED', str(item['signal'].ts), str(tick_timestamp)))
                            active.remove(item)
                advance_row()

        def persist_trade_snapshot() -> None:
            prior = progress.get('trades', [])
            progress['trades'] = prior + [asdict(trade) for trade in trades if asdict(trade) not in prior]
            self._checkpoint_runtime_state(progress)
            progress['tick_replay_state'] = self._serialize_active_tick_replay(active)
            progress['tick_replay_state']['tick_cursor'] = {
                'stream_start': str(stream_start),
                'stream_end': str(stream_end),
                'processed_tick_count': processed_tick_count,
            }

        signal = first_signal
        seen_signal = False
        while signal is not None:
            if seen_signal:
                process_until(pd.Timestamp(signal.ts), inclusive=False)
            self._manage_active_positions(active, trades, signal)
            if signal.decision in {'BUY', 'SELL'}:
                execution_count += 1
                mode, max_positions = self._sync_trading_mode()
                entry = float(signal.context['m5']['Close'].iloc[-1])
                sl, tp, plan = self._plan_for_signal(signal, mode)
                if not plan.valid:
                    trades.append(TradeExecutionResult(0, signal.decision, entry, sl, tp, entry, 'INVALID_PLAN', 0.0, 'REJECTED', str(signal.ts), str(signal.ts)))
                else:
                    tp = plan.tp
                    session = self._replay_session(signal.ts)
                    allowed, limit_reason = self.trade_manager.allow_entry(
                        signal.ts,
                        session,
                        news_blocked=self._news_blocked_at(signal.ts),
                        max_open_positions=max_positions,
                    )
                    if not allowed:
                        trades.append(TradeExecutionResult(0, signal.decision, entry, sl, tp, entry, limit_reason, 0.0, 'REJECTED', str(signal.ts), str(signal.ts)))
                    else:
                        self.trade_manager.record_entry()
                        trade = self.order_sim.create_order(signal.decision, entry, sl, tp, plan.position_size, session=session, score_info={'decision': signal.decision})
                        active.append({
                            'signal': signal,
                            'trade': trade,
                            'raw_entry': entry,
                            'sl': sl,
                            'tp': tp,
                            'trade_end': stream_end,
                            'last_price': entry,
                            'last_timestamp': signal.ts,
                            'tick_count': 0,
                            'initial_risk': abs(entry - sl) or 1e-8,
                            'highest_r': 0.0,
                            'breakeven': False,
                            'news_protected': False,
                        })
            process_until(pd.Timestamp(signal.ts))
            seen_signal = True
            progress['trades_executed'] = execution_count
            progress['current_stage'] = 'trade_execution'
            if checkpoint is not None:
                progress['m5_candles_processed'] = signal.m5_index + 1
                progress['m5_candle_timestamp'] = str(signal.ts)
                persist_trade_snapshot()
                checkpoint.maybe_write(signal.m5_index + 1, progress)
            signal = next(signal_iter, None)

        while next_row is not None and active:
            process_until(pd.Timestamp(next_row.timestamp))
        finish_expired(stream_end + pd.Timedelta(microseconds=1))
        return trades, execution_count

    def run(self, start_date: Optional[str] = None, end_date: Optional[str] = None, window: Optional[int] = None, use_ticks: bool = True, checkpoint_path: Optional[Path | str] = None, checkpoint_interval: int = 100, resume: bool = True, cleanup_checkpoint: bool = True) -> Dict[str, Any]:
        h4_df, h1_df, m5_df = self._load_historical_data(start_date=start_date, end_date=end_date)
        m5_df = self._select_window(m5_df, window)
        if hasattr(self.tick_loader, "set_requested_period"):
            self.tick_loader.set_requested_period(start_date, end_date)
        resume_fingerprint = self._resume_fingerprint(h4_df, h1_df, m5_df, start_date, end_date, window, use_ticks)
        target_period = {
            'start': str(m5_df['timestamp'].min()) if not m5_df.empty else start_date,
            'end': str(m5_df['timestamp'].max()) if not m5_df.empty else end_date,
            'requested_start': start_date,
            'requested_end': end_date,
            'window': window,
        }
        persistence = BacktestRunPersistence.start_or_resume(
            self.project_root,
            target_period,
            'B2' if self.config.use_b2 else 'local',
            'engine_before_backtest.py',
            checkpoint_interval,
            total_units=len(m5_df),
            checkpoint_path=checkpoint_path if resume else None,
            resume_fingerprint=resume_fingerprint,
            resume=resume,
            strict_explicit=True,
        )
        self.journal.records = []
        checkpoint = persistence.checkpoint
        resume_at = 0
        saved: Dict[str, Any] = {}
        if resume and persistence.saved:
            saved = dict(persistence.saved)
            resume_at = int(saved.get('m5_candles_processed', 0))
            if resume_at < 0 or resume_at > len(m5_df):
                raise ValueError('Checkpoint M5 position is outside the replay window')
            if resume_at and saved.get('m5_candle_timestamp') != str(m5_df.iloc[resume_at - 1]['timestamp']):
                raise ValueError('Checkpoint M5 position does not match the replay window')
            self._validate_simulator_state(saved.get('simulator_state'))
            if not isinstance(saved.get('trade_manager_state'), dict):
                raise ValueError('Checkpoint lacks complete trade manager state; refusing unsafe resume')
            self._validate_tick_replay_state(saved.get('tick_replay_state'))
            if resume_at and 'signal_state' not in saved:
                raise ValueError('Checkpoint lacks complete signal state; refusing unsafe resume')
            if 'signal_state' in saved:
                self._validate_signal_state(saved['signal_state'])
            self.order_sim.restore(saved['simulator_state'])
            self.trade_manager.restore(saved['trade_manager_state'])
            self._restore_active_tick_replay(saved['tick_replay_state'])
        progress: Dict[str, Any] = {
            'm5_candles_processed': resume_at,
            'm5_candle_timestamp': str(m5_df.iloc[resume_at - 1]['timestamp']) if resume_at else None,
            'h1_candles_loaded': saved.get('h1_candles_loaded', len(h1_df)),
            'h4_candles_loaded': saved.get('h4_candles_loaded', len(h4_df)),
            'signals_generated': saved.get('signals_generated', 0),
            'trades_executed': saved.get('trades_executed', 0),
            'ticks_processed': saved.get('ticks_processed', 0),
            'tick_loader_calls': saved.get('tick_loader_calls', 0),
            'current_stage': saved.get('current_stage', 'data_loaded'),
            'errors': saved.get('errors', []),
            'warnings': saved.get('warnings', []),
            'no_lookahead_violations': saved.get('no_lookahead_violations', 0),
        }
        if persistence.saved.get('trades'):
            progress['trades'] = persistence.saved['trades']
        self._checkpoint_runtime_state(progress)
        progress['tick_replay_state'] = saved.get('tick_replay_state', {'active_positions': []})
        self._run_tick_data = None
        self._run_news_data = self.news_loader.load()
        self._feature_cache.clear()
        if use_ticks and self.tick_loader.available():
            progress['current_stage'] = 'loading_ticks'
            self._run_tick_data = self.tick_loader
            progress['tick_loader_calls'] = 1
        if saved:
            tick_state = saved['tick_replay_state']
            has_tick_state = bool(tick_state['active_positions']) or tick_state.get('tick_cursor') is not None
            if has_tick_state and (not use_ticks or self._run_tick_data is None):
                raise ValueError('Tick replay checkpoint state cannot be resumed without tick data')
            if resume_at and use_ticks and self._run_tick_data is not None and tick_state.get('tick_cursor') is None:
                raise ValueError('Tick replay checkpoint cursor is missing; refusing unsafe resume')
        if checkpoint is not None and not saved:
            checkpoint.write(progress)
        progress['current_stage'] = 'signal_generation'
        signal_state: Dict[str, Any] = saved.get('signal_state', {})

        signal_iter = self._signals_for_window(
            h4_df,
            h1_df,
            m5_df,
            checkpoint if not use_ticks else None,
            progress,
            start_idx=resume_at,
            state=signal_state,
        )
        if use_ticks and self._run_tick_data is not None:
            trades, execution_count = self._chronological_tick_replay(
                signal_iter,
                m5_df,
                progress,
                checkpoint,
                resume_state=saved.get('tick_replay_state'),
            )
        else:
            trades = []
            execution_count = 0
            for signal in signal_iter:
                if signal.decision not in {'BUY', 'SELL'}:
                    continue
                execution_count += 1
                trade_result = TradeExecutionResult(
                    ticket=0,
                    direction=signal.decision,
                    entry=float(signal.context['m5']['Close'].iloc[-1]),
                    sl=0.0,
                    tp=0.0,
                    exit_price=float(signal.context['m5']['Close'].iloc[-1]),
                    exit_reason='NO_TICK_DATA',
                    pnl=0.0,
                    status='SKIPPED',
                    open_time=str(signal.ts),
                    close_time=str(signal.ts),
                )
                trades.append(trade_result)

        if persistence.saved.get('trades'):
            restored_trades = [TradeExecutionResult(**item) for item in persistence.saved['trades']]
            trades = restored_trades + trades

        for trade_result in trades:
            if trade_result.status in {'CLOSED', 'REJECTED'} or trade_result.exit_reason == 'NO_TICK_DATA':
                trade_record = TradeRecord(
                    ticket=int(trade_result.ticket) if trade_result.ticket else 0,
                    symbol=self.config.symbol,
                    direction=trade_result.direction,
                    entry=trade_result.entry,
                    sl=trade_result.sl,
                    tp=trade_result.tp,
                    lot_size=0.0,
                    open_time=trade_result.open_time,
                    close_time=trade_result.close_time,
                    exit_price=trade_result.exit_price,
                    exit_reason=trade_result.exit_reason,
                    pnl=trade_result.pnl,
                    rr_ratio=0.0,
                    status=trade_result.status,
                    session='LONDON',
                )
                self.journal.add(trade_record)
        progress['trades_executed'] = execution_count
        progress['current_stage'] = 'trade_execution'
        if checkpoint is not None:
            checkpoint.maybe_write(execution_count, progress)

        counters = signal_state['counters']
        warnings = signal_state['warnings']
        reasons = signal_state['reasons']
        signals_generated = signal_state['signals_generated']

        self.performance.add_trades([
            {
                'symbol': self.config.symbol,
                'direction': r.direction,
                'pnl': r.pnl,
                'exit_reason': r.exit_reason,
            } for r in trades if r.status == 'CLOSED'
        ])

        summary = {
            'test_period': {
                'start': str(m5_df['timestamp'].min()) if not m5_df.empty else None,
                'end': str(m5_df['timestamp'].max()) if not m5_df.empty else None,
            },
            'candles_processed': int(len(m5_df)),
            'signals_generated': int(signals_generated),
            'buy_count': int(counters['buy']),
            'sell_count': int(counters['sell']),
            'no_trade_count': int(counters['no_trade']),
            'warmup_skipped': int(counters['warmup_skipped']),
            'lookahead_violations': int(counters['lookahead_violations']),
            'trades_simulated': int(len(trades)),
            'performance': self.performance.report(),
            'warnings': warnings,
            'reasons': reasons,
            'tick_data_available': bool(self.tick_loader.available()),
            'live_mt5_orders_sent': False,
            'main_file_untouched': True,
        }
        if checkpoint is not None:
            progress.update({
                'm5_candles_processed': len(m5_df),
                'signals_generated': signals_generated,
                'trades_executed': len(trades),
                'current_stage': 'completed',
                'no_lookahead_violations': counters['lookahead_violations'],
                'warnings': warnings,
            })
            summary['persistent_artifacts'] = persistence.finalize(
                progress,
                summary,
                self.journal,
                cleanup_checkpoint=cleanup_checkpoint,
            )
        return summary

    def export_results(self, csv_path: Optional[Path | str] = None, json_path: Optional[Path | str] = None) -> Dict[str, str]:
        csv_out = self.journal.export_csv(csv_path)
        json_out = self.journal.export_json(json_path)
        return {'csv': str(csv_out), 'json': str(json_out)}
