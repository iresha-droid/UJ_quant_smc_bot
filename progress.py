from __future__ import annotations

import json
import logging
import os
import resource
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


logger = logging.getLogger(__name__)


class BacktestProgressCheckpoint:
    """Durably persist the latest external backtest progress snapshot."""

    def __init__(
        self,
        path: Path | str,
        interval: int = 100,
        total_units: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None,
        persist: Optional[Callable[[Path], None]] = None,
    ):
        self.path = Path(path)
        self.interval = max(1, int(interval))
        self.total_units = max(1, int(total_units)) if total_units else None
        self.milestones = {20, 40, 60, 80, 100}
        self.persisted_milestones: set[int] = set()
        self.metadata = dict(metadata or {})
        self.persist = persist
        self.started_at = time.time()
        self.processed = 0
        self.last_snapshot: Dict[str, Any] = {}

    def should_write(self, processed: int, force: bool = False) -> bool:
        if force or processed == 1 or processed % self.interval == 0:
            return True
        if self.total_units is None:
            return False
        reached = {
            milestone for milestone in self.milestones
            if processed * 100 >= self.total_units * milestone
        }
        return bool(reached - self.persisted_milestones)

    def write(self, snapshot: Dict[str, Any]) -> None:
        payload = dict(self.metadata)
        payload.update(snapshot)
        payload.setdefault("status", "ONGOING")
        payload["checkpoint_timestamp"] = time.time()
        payload["elapsed_seconds"] = round(time.time() - self.started_at, 3)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        payload["cpu_user_seconds"] = round(usage.ru_utime, 3)
        payload["cpu_system_seconds"] = round(usage.ru_stime, 3)
        payload["rss_bytes"] = int(usage.ru_maxrss * 1024)
        if self.total_units:
            processed = int(payload.get("m5_candles_processed", 0))
            self.persisted_milestones.update(
                milestone for milestone in self.milestones
                if processed * 100 >= self.total_units * milestone
            )
            payload["checkpoint_milestones"] = sorted(self.persisted_milestones)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(self.path)
        self.last_snapshot = payload
        if self.persist is not None:
            self.persist(self.path)

    def read(self) -> Dict[str, Any]:
        with self.path.open("r", encoding="utf-8") as handle:
            snapshot = json.load(handle)
        if not isinstance(snapshot, dict):
            raise ValueError("Checkpoint must contain a JSON object")
        return snapshot

    def maybe_write(self, processed: int, snapshot: Dict[str, Any], force: bool = False) -> None:
        if self.should_write(processed, force=force):
            self.write(snapshot)

    def close(self, snapshot: Dict[str, Any]) -> None:
        self.write(snapshot)


class BacktestRunPersistence:
    """Own run-scoped checkpoints and permanent result artifacts."""

    def __init__(
        self,
        project_root: Path,
        target_period: Dict[str, Any],
        data_source: str,
        strategy_reference: str,
        checkpoint_interval: int = 100,
        total_units: Optional[int] = None,
        checkpoint_path: Optional[Path | str] = None,
        saved: Optional[Dict[str, Any]] = None,
        resume_fingerprint: Optional[str] = None,
    ):
        self.project_root = Path(project_root)
        self.results_dir = self.project_root / "data" / "backtest_results"
        self.checkpoints_dir = self.project_root / "data" / "backtest_checkpoints"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoints_dir.mkdir(parents=True, exist_ok=True)
        self.target_period = dict(target_period)
        self.data_source = data_source
        self.strategy_reference = strategy_reference
        self.resume_fingerprint = resume_fingerprint
        self.saved = saved or {}
        self.run_id = str(self.saved.get("run_id") or self._new_run_id())
        self.checkpoint_path = Path(checkpoint_path) if checkpoint_path else self.checkpoints_dir / f"backtest_{self.run_id}_checkpoint.json"
        metadata = {
            "run_id": self.run_id,
            "status": "ONGOING",
            "target_period": self.target_period,
            "start_time": self.saved.get("start_time") or datetime.now(timezone.utc).isoformat(),
            "data_source": self.data_source,
            "strategy_reference": self.strategy_reference,
            "resume_fingerprint": self.resume_fingerprint,
        }
        self.metadata = metadata
        # Google Drive is the PRIMARY remote runtime checkpoint/status persistence
        # target, independent of `data_source`; it is always attached here.
        self.checkpoint = BacktestProgressCheckpoint(
            self.checkpoint_path,
            checkpoint_interval,
            total_units=total_units,
            metadata=metadata,
            persist=self._persist_checkpoint,
        )
        self._b2_client = None

    def _persist_checkpoint(self, path: Path) -> None:
        import drive_persistence

        try:
            drive_persistence.upload_checkpoint(path)
        except Exception as exc:
            logger.warning(
                "Google Drive checkpoint sync unavailable; local checkpoint retained: %s",
                exc,
            )
        # B2 is an optional, non-blocking secondary backup only; it never
        # gates Google Drive persistence or local checkpoint continuity.
        if self.data_source == "B2":
            self._persist_checkpoint_to_b2(path)

    def _persist_checkpoint_to_b2(self, path: Path) -> None:
        from backup_system.b2_backup import get_client, synchronize_file

        try:
            if self._b2_client is None:
                self._b2_client = get_client()
            synchronize_file(self._b2_client, path)
        except Exception as exc:
            logger.warning(
                "B2 checkpoint backup unavailable; local checkpoint retained: %s",
                exc,
            )

    @staticmethod
    def _new_run_id() -> str:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        return f"{stamp}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def _read_checkpoint(path: Path) -> Optional[Dict[str, Any]]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            return payload if isinstance(payload, dict) else None
        except (OSError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _validate_explicit_checkpoint(
        project_root: Path,
        path: Path,
        saved: Optional[Dict[str, Any]],
        target_period: Dict[str, Any],
        data_source: str,
        strategy_reference: str,
        resume_fingerprint: Optional[str],
    ) -> Dict[str, Any]:
        if saved is None:
            raise ValueError("Explicit resume checkpoint is missing, unreadable, or malformed")

        run_id = saved.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise ValueError("Explicit resume checkpoint is missing a valid run_id")
        result_path = Path(project_root) / "data" / "backtest_results" / f"backtest_{run_id}_summary.json"
        if result_path.exists():
            result_summary = BacktestRunPersistence._read_checkpoint(result_path)
            if (
                result_summary is None
                or result_summary.get("run_id") != run_id
                or result_summary.get("status") != "COMPLETED"
            ):
                raise ValueError("Explicit resume checkpoint has an unverifiable linked result summary")
            raise ValueError("Explicit resume checkpoint already has a completed result")

        prefix, suffix = "backtest_", "_checkpoint.json"
        if path.name.startswith(prefix) and path.name.endswith(suffix):
            expected_run_id = path.name[len(prefix):-len(suffix)]
            if not expected_run_id or run_id != expected_run_id:
                raise ValueError("Explicit resume checkpoint run_id does not match its filename")

        if saved.get("status") != "ONGOING":
            raise ValueError("Explicit resume checkpoint status must be ONGOING")
        saved_target = saved.get("target_period")
        if not isinstance(saved_target, dict) or any(
            key not in saved_target or saved_target[key] != value
            for key, value in target_period.items()
        ):
            raise ValueError("Explicit resume checkpoint target period does not match")
        if saved.get("data_source") != data_source:
            raise ValueError("Explicit resume checkpoint data source does not match")
        if saved.get("strategy_reference") != strategy_reference:
            raise ValueError("Explicit resume checkpoint strategy identity does not match")
        if not isinstance(saved.get("resume_fingerprint"), str) or saved.get("resume_fingerprint") != resume_fingerprint:
            raise ValueError("Checkpoint replay identity does not match; refusing unsafe resume")

        processed = saved.get("m5_candles_processed")
        if type(processed) is not int or processed < 0 or "m5_candle_timestamp" not in saved:
            raise ValueError("Explicit resume checkpoint progress state is malformed")
        timestamp = saved.get("m5_candle_timestamp")
        if (processed == 0 and timestamp is not None) or (
            processed > 0 and (not isinstance(timestamp, str) or not timestamp)
        ):
            raise ValueError("Explicit resume checkpoint progress state is inconsistent")

        for key in ("simulator_state", "trade_manager_state", "tick_replay_state"):
            if not isinstance(saved.get(key), dict):
                raise ValueError(f"Explicit resume checkpoint lacks valid {key}")
        if processed > 0 and not isinstance(saved.get("signal_state"), dict):
            raise ValueError("Explicit resume checkpoint lacks valid signal_state")
        return saved

    @classmethod
    def start_or_resume(
        cls,
        project_root: Path,
        target_period: Dict[str, Any],
        data_source: str,
        strategy_reference: str,
        checkpoint_interval: int = 100,
        total_units: Optional[int] = None,
        checkpoint_path: Optional[Path | str] = None,
        resume_fingerprint: Optional[str] = None,
        resume: bool = True,
        strict_explicit: bool = False,
    ) -> "BacktestRunPersistence":
        candidate: Optional[Path] = Path(checkpoint_path) if checkpoint_path and resume else None
        saved: Optional[Dict[str, Any]] = None
        if candidate is not None:
            saved = cls._read_checkpoint(candidate)
            if strict_explicit:
                cls._validate_explicit_checkpoint(
                    project_root,
                    candidate,
                    saved,
                    target_period,
                    data_source,
                    strategy_reference,
                    resume_fingerprint,
                )
            elif saved and saved.get("resume_fingerprint") != resume_fingerprint:
                raise ValueError("Checkpoint replay identity does not match; refusing unsafe resume")
        elif resume:
            checkpoint_dir = Path(project_root) / "data" / "backtest_checkpoints"
            ongoing = []
            for path in checkpoint_dir.glob("backtest_*_checkpoint.json"):
                saved = cls._read_checkpoint(path)
                if not saved or saved.get("status") == "COMPLETED":
                    continue
                if saved.get("strategy_reference") != strategy_reference:
                    continue
                if saved.get("resume_fingerprint") != resume_fingerprint:
                    continue
                saved_target = saved.get("target_period") or {}
                if any(saved_target.get(key) != target_period.get(key) for key in target_period):
                    continue
                ongoing.append((saved.get("checkpoint_timestamp", 0), path, saved))
            if ongoing:
                _, candidate, saved = max(ongoing, key=lambda item: item[0])
                return cls(project_root, target_period, data_source, strategy_reference, checkpoint_interval, total_units, candidate, saved, resume_fingerprint)
            saved = None
        return cls(project_root, target_period, data_source, strategy_reference, checkpoint_interval, total_units, candidate, saved, resume_fingerprint)

    def finalize(
        self,
        progress: Dict[str, Any],
        summary: Dict[str, Any],
        journal: Any,
        cleanup_checkpoint: bool = True,
    ) -> Dict[str, str]:
        csv_path = self.results_dir / f"backtest_{self.run_id}_trades.csv"
        trades_path = self.results_dir / f"backtest_{self.run_id}_trades.json"
        summary_path = self.results_dir / f"backtest_{self.run_id}_summary.json"
        journal.export_csv(csv_path)
        journal.export_json(trades_path)
        final_summary = dict(summary)
        final_summary.update({"run_id": self.run_id, "status": "COMPLETED", "target_period": self.target_period, "strategy_reference": self.strategy_reference, "trade_result_file": str(trades_path), "trade_csv_file": str(csv_path), "lookahead_validation": {"violations": int(progress.get("no_lookahead_violations", 0)), "passed": int(progress.get("no_lookahead_violations", 0)) == 0}, "final_progress": dict(progress)})
        temporary = summary_path.with_suffix(summary_path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(final_summary, handle, indent=2, default=str)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(summary_path)
        # Final results/status are persisted to Google Drive independently of the
        # detached launcher path and independently of B2 availability/outcome.
        self._persist_final_results_to_drive(csv_path, trades_path, summary_path)
        if cleanup_checkpoint:
            self.checkpoint.path.unlink(missing_ok=True)
        else:
            completed = dict(progress)
            completed.update({"status": "COMPLETED", "current_stage": "completed", "final_result": str(summary_path)})
            self.checkpoint.write(completed)
        return {
            "csv": str(csv_path),
            "trades": str(trades_path),
            "summary": str(summary_path),
            "checkpoint": str(self.checkpoint.path),
        }

    def _persist_final_results_to_drive(self, *paths: Path) -> None:
        import drive_persistence

        for path in paths:
            try:
                drive_persistence.upload_result_artifact(path)
            except Exception as exc:
                logger.warning(
                    "Google Drive result sync unavailable for %s; local artifact retained: %s",
                    path.name,
                    exc,
                )

    def read(self) -> Dict[str, Any]:
        return self.checkpoint.read()
