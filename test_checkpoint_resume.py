from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from engine import HistoricalBacktestEngine, SignalEvent
from config import BacktestConfig
from order_simulator import OrderSimulator
from progress import BacktestProgressCheckpoint, BacktestRunPersistence
from trade_manager import TradeManager


class CapturingCheckpoint:
    def __init__(self):
        self.snapshots = []

    def maybe_write(self, processed, snapshot):
        self.snapshots.append((processed, copy.deepcopy(snapshot)))


class SyntheticTickLoader:
    def __init__(self, ticks):
        self.ticks = ticks

    def iter_chunks(self, start_date=None, end_date=None):
        start = pd.Timestamp(start_date) if start_date else None
        end = pd.Timestamp(end_date) if end_date else None
        chunk = self.ticks
        if start is not None:
            chunk = chunk[chunk['timestamp'] >= start]
        if end is not None:
            chunk = chunk[chunk['timestamp'] <= end]
        if not chunk.empty:
            yield chunk.reset_index(drop=True)


class _StubStructure(Enum):
    NEUTRAL = "neutral"
    BEARISH_CHOCH = "bearish_choch"
    BULLISH_CHOCH = "bullish_choch"


class SyntheticProduction:
    Structure = _StubStructure

    def __init__(self):
        self.state = SimpleNamespace(balance=10000.0, mode="SPLIT_ENTRY")

    def update_trading_mode(self):
        self.state.mode = "SINGLE_TRADE" if self.state.balance < 100.0 else "SPLIT_ENTRY"

    def get_max_open_positions(self):
        return 2 if self.state.mode == "SPLIT_ENTRY" else 1

    @staticmethod
    def check_market_regime(_df):
        return {"regime": "TRENDING", "adx": 25.0, "size_multiplier": 1.0}

    @staticmethod
    def get_symbol_specs(_symbol):
        return {"lot_step": 0.01, "min_lot": 0.01}

    @staticmethod
    def calculate_sl_tp(*_args):
        return 90.0, 102.0

    @staticmethod
    def validate_trade(_direction, _entry, _sl, tp, _balance, _symbol, allow_no_tp=False):
        return SimpleNamespace(valid=True, position_size=1.0, tp=tp)

    @staticmethod
    def detect_bos_choch(_df):
        return _StubStructure.NEUTRAL, {}

    @staticmethod
    def _get_atr(_df, period=14):
        return 0.0

    @staticmethod
    def calculate_trailing_sl(_direction, current_sl, _entry, _df, _current_r):
        return current_sl, False


def make_engine(ticks):
    engine = HistoricalBacktestEngine.__new__(HistoricalBacktestEngine)
    engine.config = SimpleNamespace(
        symbol='XAUUSD',
        news_protection=False,
        initial_balance=10000.0,
        allow_no_tp=True,
    )
    engine.order_sim = OrderSimulator()
    engine.trade_manager = TradeManager(engine.order_sim)
    engine.production_module = SyntheticProduction()
    engine._run_tick_data = SyntheticTickLoader(ticks)
    engine._run_news_data = None
    return engine


def make_signal(index, timestamp, details):
    frame = pd.DataFrame({'Close': [100.0], 'High': [100.0], 'Low': [100.0]})
    return SignalEvent(
        ts=pd.Timestamp(timestamp),
        m5_index=index,
        decision='BUY' if index == 0 else 'NO SETUP',
        long_score=7.5,
        short_score=1.25,
        context={'m5': frame, 'h1': frame, 'h4': frame},
        details=details,
    )


class CheckpointResumeTests(unittest.TestCase):
    def setUp(self):
        self.ticks = pd.DataFrame({
            'timestamp': pd.to_datetime([
                '2026-01-01 10:00:00', '2026-01-01 10:00:00',
                '2026-01-01 10:01:00', '2026-01-01 10:05:00',
            ]),
            'bid': [100.0, 100.5, 101.0, 103.0],
            'ask': [100.1, 100.6, 101.1, 103.1],
        })
        self.m5 = pd.DataFrame({'timestamp': pd.to_datetime([
            '2026-01-01 10:00:00', '2026-01-01 10:05:00',
        ])})

    def _make_explicit_resume_fixture(self, root):
        h4 = pd.DataFrame({'timestamp': pd.to_datetime(['2025-12-31 16:00:00'])})
        h1 = pd.DataFrame({'timestamp': pd.to_datetime(['2025-12-31 20:00:00'])})
        m5 = pd.DataFrame({'timestamp': pd.to_datetime([
            '2026-01-01 00:00:00', '2026-01-01 00:05:00', '2026-01-01 00:10:00',
        ])})
        engine = HistoricalBacktestEngine.__new__(HistoricalBacktestEngine)
        engine.project_root = Path(root)
        engine.config = SimpleNamespace(use_b2=False)
        engine._load_historical_data = lambda **_kwargs: (h4, h1, m5)
        engine._select_window = lambda frame, _window: frame
        engine._resume_fingerprint = lambda *_args: 'fixture-fingerprint'
        engine.tick_loader = SimpleNamespace(available=lambda: True)
        engine.news_loader = SimpleNamespace(load=lambda: [])
        engine._feature_cache = {}
        engine.order_sim = OrderSimulator()
        engine.trade_manager = TradeManager(engine.order_sim)
        engine.journal = SimpleNamespace(records=[])
        timestamp = str(m5.iloc[0]['timestamp'])
        target_period = {
            'start': str(m5['timestamp'].min()),
            'end': str(m5['timestamp'].max()),
            'requested_start': '2026-01-01 00:00:00',
            'requested_end': '2026-01-01 00:10:00',
            'window': None,
        }
        payload = {
            'run_id': 'requested-run',
            'status': 'ONGOING',
            'target_period': target_period,
            'data_source': 'local',
            'strategy_reference': 'engine_before_backtest.py',
            'resume_fingerprint': 'fixture-fingerprint',
            'm5_candles_processed': 1,
            'm5_candle_timestamp': timestamp,
            'simulator_state': engine.order_sim.snapshot(),
            'trade_manager_state': engine.trade_manager.snapshot(),
            'tick_replay_state': {
                'active_positions': [],
                'tick_cursor': {
                    'stream_start': timestamp,
                    'stream_end': '2026-01-01 01:10:00',
                    'processed_tick_count': 0,
                },
            },
            'signal_state': {
                'counters': {
                    'valid_4h_context': 0,
                    'valid_1h_setup': 0,
                    'valid_5m_trigger': 0,
                    'buy': 0,
                    'sell': 0,
                    'no_trade': 0,
                    'warmup_skipped': 0,
                    'lookahead_violations': 0,
                },
                'warnings': [],
                'reasons': [],
                'signals_generated': 0,
            },
        }
        return engine, payload

    @staticmethod
    def _tree_snapshot(root):
        root = Path(root)
        return {
            path.relative_to(root): path.read_bytes()
            for path in root.rglob('*')
            if path.is_file()
        }

    def _assert_explicit_failure_has_no_side_effects(self, root, path, payload=None, directory=False, result_summary=None):
        engine, valid_payload = self._make_explicit_resume_fixture(root)
        checkpoint_dir = Path(root) / 'data' / 'backtest_checkpoints'
        checkpoint_dir.mkdir(parents=True)
        alternate_path = checkpoint_dir / 'backtest_alternate-run_checkpoint.json'
        alternate_payload = copy.deepcopy(valid_payload)
        alternate_payload.update({'run_id': 'alternate-run', 'checkpoint_timestamp': 1})
        alternate_path.write_text(json.dumps(alternate_payload), encoding='utf-8')

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if directory:
            path.mkdir()
        elif payload is not None:
            if isinstance(payload, bytes):
                path.write_bytes(payload)
            else:
                path.write_text(json.dumps(payload), encoding='utf-8')
        if result_summary is not None:
            result_path = Path(root) / 'data' / 'backtest_results' / 'backtest_requested-run_summary.json'
            result_path.parent.mkdir(parents=True, exist_ok=True)
            result_path.write_text(json.dumps(result_summary), encoding='utf-8')

        before = self._tree_snapshot(root)
        with patch.object(BacktestProgressCheckpoint, 'write') as checkpoint_write, \
                patch.object(BacktestRunPersistence, '_new_run_id', wraps=BacktestRunPersistence._new_run_id) as new_run_id, \
                patch.object(engine, '_signals_for_window', create=True) as signal_replay, \
                patch.object(engine, '_chronological_tick_replay', create=True) as tick_replay:
            with self.assertRaises(ValueError):
                engine.run(
                    start_date='2026-01-01 00:00:00',
                    end_date='2026-01-01 00:10:00',
                    checkpoint_path=path,
                )

        self.assertEqual(self._tree_snapshot(root), before)
        checkpoint_write.assert_not_called()
        new_run_id.assert_not_called()
        signal_replay.assert_not_called()
        tick_replay.assert_not_called()

    def test_invalid_explicit_resume_fails_closed_without_side_effects(self):
        cases = [
            ('missing', 'missing_checkpoint.json', None, False),
            ('unreadable', 'unreadable_checkpoint.json', None, True),
            ('corrupt JSON', 'corrupt_checkpoint.json', b'{', False),
            ('non-object JSON', 'non_object_checkpoint.json', [], False),
        ]
        for label, filename, checkpoint, directory in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory_path:
                self._assert_explicit_failure_has_no_side_effects(
                    directory_path,
                    Path(directory_path) / filename,
                    checkpoint,
                    directory,
                )

        mutations = [
            ('wrong canonical run_id', 'backtest_requested-run_checkpoint.json', lambda state: state.update({'run_id': 'other-run'})),
            ('wrong target period', 'explicit_checkpoint.json', lambda state: state['target_period'].update({'end': '2026-01-02 00:00:00'})),
            ('wrong fingerprint', 'explicit_checkpoint.json', lambda state: state.update({'resume_fingerprint': 'wrong'})),
            ('wrong source identity', 'explicit_checkpoint.json', lambda state: state.update({'data_source': 'B2'})),
            ('missing required state', 'explicit_checkpoint.json', lambda state: state.pop('trade_manager_state')),
            ('invalid status', 'explicit_checkpoint.json', lambda state: state.update({'status': 'COMPLETED'})),
            ('invalid M5 position', 'explicit_checkpoint.json', lambda state: state.update({'m5_candles_processed': -1})),
            ('invalid simulator runtime', 'explicit_checkpoint.json', lambda state: state.update({'simulator_state': {}})),
            ('invalid manager runtime', 'explicit_checkpoint.json', lambda state: state.update({'trade_manager_state': {}})),
            ('invalid active tick runtime', 'explicit_checkpoint.json', lambda state: state.update({'tick_replay_state': {'active_positions': [{}]}})),
            ('invalid tick cursor runtime', 'explicit_checkpoint.json', lambda state: state['tick_replay_state']['tick_cursor'].update({'processed_tick_count': -1})),
            ('invalid tick cursor timestamp', 'explicit_checkpoint.json', lambda state: state['tick_replay_state']['tick_cursor'].update({'stream_start': 1})),
            ('missing tick cursor', 'explicit_checkpoint.json', lambda state: state['tick_replay_state'].pop('tick_cursor')),
            ('invalid signal runtime', 'explicit_checkpoint.json', lambda state: state.update({'signal_state': {}})),
            ('wrong candle timestamp', 'explicit_checkpoint.json', lambda state: state.update({'m5_candle_timestamp': '2026-01-01 00:05:00'})),
        ]
        for label, filename, mutate in mutations:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as directory_path:
                _, checkpoint = self._make_explicit_resume_fixture(directory_path)
                mutate(checkpoint)
                self._assert_explicit_failure_has_no_side_effects(
                    directory_path,
                    Path(directory_path) / filename,
                    checkpoint,
                )

    def test_completed_linked_result_fails_closed_without_side_effects(self):
        with tempfile.TemporaryDirectory() as directory:
            _, checkpoint = self._make_explicit_resume_fixture(directory)
            self._assert_explicit_failure_has_no_side_effects(
                directory,
                Path(directory) / 'explicit_checkpoint.json',
                checkpoint,
                result_summary={'run_id': 'requested-run', 'status': 'COMPLETED'},
            )

    def test_custom_explicit_path_uses_existing_identity_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, saved = self._make_explicit_resume_fixture(root)
            checkpoint_path = root / 'custom_resume_target.json'
            checkpoint_path.write_text(json.dumps(saved), encoding='utf-8')

            persistence = BacktestRunPersistence.start_or_resume(
                root,
                saved['target_period'],
                saved['data_source'],
                saved['strategy_reference'],
                checkpoint_path=checkpoint_path,
                resume_fingerprint=saved['resume_fingerprint'],
                strict_explicit=True,
            )

            self.assertEqual(persistence.run_id, saved['run_id'])
            self.assertEqual(persistence.checkpoint_path, checkpoint_path)
            self.assertEqual(persistence.saved, saved)

    def test_legacy_explicit_checkpoint_state_remains_compatible(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_period = {
                'start': '2026-01-01 00:00:00',
                'end': '2026-01-01 00:10:00',
                'requested_start': '2026-01-01 00:00:00',
                'requested_end': '2026-01-01 00:10:00',
            }
            saved = {
                'run_id': 'legacy-run',
                'status': 'ONGOING',
                'target_period': target_period,
                'data_source': 'local',
                'strategy_reference': 'engine_before_backtest.py',
                'resume_fingerprint': 'legacy-fingerprint',
                'm5_candles_processed': 1,
                'm5_candle_timestamp': '2026-01-01 00:00:00',
                'simulator_state': {
                    'next_ticket': 100000,
                    'open_positions': [],
                    'closed_positions': [],
                },
            }
            checkpoint_path = root / 'backtest_legacy-run_checkpoint.json'
            checkpoint_path.write_text(json.dumps(saved), encoding='utf-8')

            persistence = BacktestRunPersistence.start_or_resume(
                root,
                target_period,
                'local',
                'engine_before_backtest.py',
                checkpoint_path=checkpoint_path,
                resume_fingerprint='legacy-fingerprint',
            )

            self.assertEqual(persistence.run_id, 'legacy-run')
            self.assertEqual(persistence.saved, saved)

    def test_new_run_does_not_select_automatic_checkpoint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_period = {
                'start': '2026-01-01 00:00:00',
                'end': '2026-01-01 00:10:00',
                'requested_start': '2026-01-01 00:00:00',
                'requested_end': '2026-01-01 00:10:00',
                'window': None,
            }
            checkpoint_dir = root / 'data' / 'backtest_checkpoints'
            checkpoint_dir.mkdir(parents=True)
            candidate = checkpoint_dir / 'backtest_existing-run_checkpoint.json'
            candidate.write_text(json.dumps({
                'run_id': 'existing-run',
                'status': 'ONGOING',
                'target_period': target_period,
                'strategy_reference': 'engine_before_backtest.py',
                'resume_fingerprint': 'fingerprint',
                'checkpoint_timestamp': 10,
            }), encoding='utf-8')

            with patch.object(BacktestRunPersistence, '_new_run_id', return_value='new-run'):
                persistence = BacktestRunPersistence.start_or_resume(
                    root,
                    target_period,
                    'local',
                    'engine_before_backtest.py',
                    resume_fingerprint='fingerprint',
                    resume=False,
                )

            self.assertEqual(persistence.run_id, 'new-run')
            self.assertEqual(persistence.saved, {})
            self.assertNotEqual(persistence.checkpoint_path, candidate)
            self.assertTrue(candidate.is_file())

    def test_automatic_recovery_selection_remains_intact(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_period = {
                'start': '2026-01-01 00:00:00',
                'end': '2026-01-01 00:10:00',
                'requested_start': '2026-01-01 00:00:00',
                'requested_end': '2026-01-01 00:10:00',
                'window': None,
            }
            checkpoint_dir = root / 'data' / 'backtest_checkpoints'
            checkpoint_dir.mkdir(parents=True)
            candidate = checkpoint_dir / 'backtest_existing-run_checkpoint.json'
            saved = {
                'run_id': 'existing-run',
                'status': 'ONGOING',
                'target_period': target_period,
                'strategy_reference': 'engine_before_backtest.py',
                'resume_fingerprint': 'fingerprint',
                'checkpoint_timestamp': 10,
            }
            candidate.write_text(json.dumps(saved), encoding='utf-8')

            persistence = BacktestRunPersistence.start_or_resume(
                root,
                target_period,
                'local',
                'engine_before_backtest.py',
                resume_fingerprint='fingerprint',
            )

            self.assertEqual(persistence.run_id, 'existing-run')
            self.assertEqual(persistence.checkpoint_path, candidate)
            self.assertEqual(persistence.saved, saved)

    def test_automatic_recovery_skips_nonmatching_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target_period = {
                'start': '2026-01-01 00:00:00',
                'end': '2026-01-01 00:10:00',
                'requested_start': '2026-01-01 00:00:00',
                'requested_end': '2026-01-01 00:10:00',
                'window': None,
            }
            checkpoint_dir = root / 'data' / 'backtest_checkpoints'
            checkpoint_dir.mkdir(parents=True)
            candidate = checkpoint_dir / 'backtest-other-run_checkpoint.json'
            candidate.write_text(json.dumps({
                'run_id': 'other-run',
                'status': 'ONGOING',
                'target_period': dict(target_period, end='2026-01-02 00:00:00'),
                'strategy_reference': 'engine_before_backtest.py',
                'resume_fingerprint': 'fingerprint',
                'checkpoint_timestamp': 10,
            }), encoding='utf-8')

            with patch.object(BacktestRunPersistence, '_new_run_id', return_value='new-run'):
                persistence = BacktestRunPersistence.start_or_resume(
                    root,
                    target_period,
                    'local',
                    'engine_before_backtest.py',
                    resume_fingerprint='fingerprint',
                )

            self.assertEqual(persistence.run_id, 'new-run')
            self.assertEqual(persistence.saved, {})
            self.assertNotEqual(persistence.checkpoint_path, candidate)
            self.assertTrue(candidate.is_file())

    def test_resume_matches_uninterrupted_with_duplicate_ticks(self):
        details = {'source': 'synthetic', 'score': {'long': 7.5}}
        first = make_signal(0, '2026-01-01 10:00:00', details)
        second = make_signal(1, '2026-01-01 10:05:00', {})

        uninterrupted = make_engine(self.ticks)
        uninterrupted_progress = {'ticks_processed': 0, 'signals_generated': 2}
        uninterrupted_trades, _ = uninterrupted._chronological_tick_replay(
            iter([first, second]), self.m5, uninterrupted_progress, CapturingCheckpoint()
        )

        interrupted = make_engine(self.ticks)
        checkpoint = CapturingCheckpoint()
        interrupted_progress = {'ticks_processed': 0, 'signals_generated': 1}

        def stop_after_first():
            yield first
            raise RuntimeError('simulated interruption')

        with self.assertRaisesRegex(RuntimeError, 'simulated interruption'):
            interrupted._chronological_tick_replay(
                stop_after_first(), self.m5, interrupted_progress, checkpoint
            )

        processed, saved = checkpoint.snapshots[-1]
        self.assertEqual(processed, 1)
        self.assertEqual(saved['m5_candles_processed'], 1)
        self.assertEqual(saved['m5_candle_timestamp'], '2026-01-01 10:00:00')
        self.assertEqual(saved['tick_replay_state']['tick_cursor']['processed_tick_count'], 2)
        self.assertEqual(
            saved['tick_replay_state']['active_positions'][0]['details'], details
        )

        resumed = make_engine(self.ticks)
        resumed.order_sim.restore(saved['simulator_state'])
        resumed.trade_manager.restore(saved['trade_manager_state'])
        restored_active = resumed._restore_active_tick_replay(saved['tick_replay_state'])
        self.assertEqual(restored_active[0]['signal'].details, details)
        resumed_progress = copy.deepcopy(saved)
        resumed_trades, _ = resumed._chronological_tick_replay(
            iter([second]), self.m5, resumed_progress,
            CapturingCheckpoint(), saved['tick_replay_state'],
        )

        self.assertEqual(
            [trade.__dict__ for trade in resumed_trades],
            [trade.__dict__ for trade in uninterrupted_trades],
        )
        self.assertEqual(resumed.order_sim.snapshot(), uninterrupted.order_sim.snapshot())
        self.assertEqual(resumed.trade_manager.snapshot(), uninterrupted.trade_manager.snapshot())
        self.assertEqual(resumed_progress['ticks_processed'], 4)

    def test_incomplete_runtime_state_is_rejected(self):
        engine = make_engine(self.ticks)
        with self.assertRaisesRegex(ValueError, 'malformed'):
            engine._validate_simulator_state({})
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            engine.trade_manager.restore({})
        with self.assertRaisesRegex(ValueError, 'malformed'):
            engine._restore_active_tick_replay({'active_positions': [{}]})

    def _write_local_fixture(self, root):
        m5_rows = []
        tick_rows = ['timestamp,bid,ask,volume']
        for index in range(31):
            timestamp = pd.Timestamp('2026-01-01 00:00:00') + pd.Timedelta(minutes=5 * index)
            price = 100.0 + index * 0.01
            m5_rows.append(f'{timestamp:%Y-%m-%d %H:%M:%S}\t{price}\t{price + 0.1}\t{price - 0.1}\t{price}\t1')
            tick_rows.append(f'{timestamp:%Y-%m-%d %H:%M:%S},{price},{price + 0.01},1')
        ohlcv = 'timestamp\topen\thigh\tlow\tclose\tvolume\n' + '\n'.join(m5_rows) + '\n'
        (root / 'XAUUSD_M5_6M.csv').write_text(ohlcv, encoding='utf-8')
        h1_rows = [
            '2025-12-31 20:00:00\t99\t100\t98\t99.5\t1',
            '2025-12-31 21:00:00\t99.5\t100.5\t99\t100\t1',
        ]
        h4_rows = [
            '2025-12-31 16:00:00\t99\t100\t98\t99.5\t1',
            '2025-12-31 20:00:00\t99.5\t100.5\t99\t100\t1',
        ]
        (root / 'XAUUSD_H1_6M.csv').write_text('timestamp\topen\thigh\tlow\tclose\tvolume\n' + '\n'.join(h1_rows) + '\n', encoding='utf-8')
        (root / 'XAUUSD_H4_6M.csv').write_text('timestamp\topen\thigh\tlow\tclose\tvolume\n' + '\n'.join(h4_rows) + '\n', encoding='utf-8')
        (root / 'XAUUSD_TICKS_6M.csv').write_text('\n'.join(tick_rows) + '\n', encoding='utf-8')
        (root / 'XAUUSD_6M_calendar.csv').write_text('time,name,currency,impact\n2025.12.01 00:00:00,Fixture,USD,low\n', encoding='utf-8')
        shutil.copy(Path(__file__).with_name('engine_before_backtest.py'), root / 'engine_before_backtest.py')

    def _fixture_config(self, root, **overrides):
        config = BacktestConfig(project_root=root, use_b2=False)
        config.news_protection = False
        for key, value in overrides.items():
            setattr(config, key, value)
        return config

    def test_run_resume_matches_uninterrupted_and_rejects_fingerprint_drift(self):
        with tempfile.TemporaryDirectory() as directory, \
                patch('drive_sync.sync_checkpoint', return_value=True), \
                patch('drive_sync.sync_result_artifact', return_value=True), \
                patch('backup_system.b2_backup.get_client', return_value=object()), \
                patch('backup_system.b2_backup.synchronize_file', return_value=True):
            root = Path(directory)
            self._write_local_fixture(root)
            checkpoint_path = root / 'interrupted_checkpoint.json'
            run_args = {
                'start_date': '2026-01-01 00:00:00',
                'end_date': '2026-01-01 02:30:00',
                'checkpoint_interval': 1,
            }

            uninterrupted = HistoricalBacktestEngine(root, self._fixture_config(root))
            uninterrupted_summary = uninterrupted.run(**run_args, resume=False)

            interrupted = HistoricalBacktestEngine(root, self._fixture_config(root))
            replay = interrupted._chronological_tick_replay

            def interrupt_after_checkpoint(signal_iter, *args, **kwargs):
                def interrupted_signals():
                    yield next(signal_iter)
                    raise RuntimeError('simulated interruption')
                return replay(interrupted_signals(), *args, **kwargs)

            interrupted._chronological_tick_replay = interrupt_after_checkpoint
            with self.assertRaisesRegex(RuntimeError, 'simulated interruption'):
                interrupted.run(**run_args, resume=False)

            checkpoint_path = next((root / 'data' / 'backtest_checkpoints').glob('backtest_*_checkpoint.json'))

            saved = json.loads(checkpoint_path.read_text(encoding='utf-8'))
            self.assertEqual(saved['m5_candles_processed'], 30)
            self.assertIn('signal_state', saved)
            self.assertIn('tick_cursor', saved['tick_replay_state'])

            drifting = HistoricalBacktestEngine(root, self._fixture_config(root, max_daily_trades=3))
            with self.assertRaisesRegex(ValueError, 'replay identity'):
                drifting.run(**run_args, checkpoint_path=checkpoint_path)

            resumed = HistoricalBacktestEngine(root, self._fixture_config(root))
            resumed_summary = resumed.run(**run_args, checkpoint_path=checkpoint_path)
            for key in ('candles_processed', 'signals_generated', 'buy_count', 'sell_count', 'no_trade_count', 'warmup_skipped', 'lookahead_violations', 'trades_simulated', 'performance', 'warnings', 'reasons'):
                self.assertEqual(resumed_summary[key], uninterrupted_summary[key])
            self.assertEqual(resumed.order_sim.snapshot(), uninterrupted.order_sim.snapshot())
            self.assertEqual(resumed.trade_manager.snapshot(), uninterrupted.trade_manager.snapshot())
            self.assertFalse(checkpoint_path.exists())
            artifacts = resumed_summary['persistent_artifacts']
            self.assertTrue(Path(artifacts['csv']).is_file())
            self.assertTrue(Path(artifacts['trades']).is_file())
            self.assertTrue(Path(artifacts['summary']).is_file())


if __name__ == '__main__':
    unittest.main()