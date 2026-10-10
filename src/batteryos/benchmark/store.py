import json
import os
import platform
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Generator

from batteryos.benchmark.environment import collect_environment
from batteryos.benchmark.workloads import describe_workload
from batteryos.logging.events import default_log_path


def default_benchmark_directory() -> Path:
    return default_log_path().parent / "benchmarks"


def _timestamp(snapshot: dict[str, Any]) -> str:
    timestamp = snapshot.get("timestamp")
    if isinstance(timestamp, str):
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except ValueError:
            pass
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class BenchmarkStore:
    def __init__(self, directory: str | Path | None = None):
        self.directory = Path(directory) if directory is not None else default_benchmark_directory()
        self.runs_directory = self.directory / "runs"
        self.active_path = self.directory / "active.json"
        self.lock_path = self.directory / ".lock"

    @contextmanager
    def _locked(self) -> Generator[None, None, None]:
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock_path.open("a+b") as lock_file:
            if platform.system() == "Windows":
                import msvcrt

                lock_file.seek(0, os.SEEK_END)
                if lock_file.tell() == 0:
                    lock_file.write(b"0")
                    lock_file.flush()
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
                try:
                    yield
                finally:
                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    @staticmethod
    def _write_json(path: Path, value: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_text(
            json.dumps(value, ensure_ascii=True, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(path)

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except json.JSONDecodeError as error:
            raise ValueError(f"Corrupt benchmark JSON: {path.name}") from error
        if not isinstance(value, dict):
            raise ValueError(f"Benchmark JSON must be an object: {path.name}")
        return value

    def _active_run_locked(self) -> dict[str, Any] | None:
        marker = self._read_json(self.active_path)
        if marker is None:
            return None
        run_id = marker.get("run_id")
        if not isinstance(run_id, str):
            raise ValueError("Active benchmark marker has no valid run_id")
        run = self._read_json(self.runs_directory / f"{run_id}.json")
        if run is None:
            raise ValueError("Active benchmark manifest is missing")
        return run

    def start(
        self,
        initial_snapshot: dict[str, Any],
        *,
        workload_name: str = "idle",
        test_name: str | None = None,
        description: str | None = None,
        interval_seconds: float = 10.0,
    ) -> dict[str, Any]:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        workload = describe_workload(workload_name, description)
        start_timestamp = _timestamp(initial_snapshot)
        chosen_test_name = (test_name or workload_name).strip()
        if not chosen_test_name:
            raise ValueError("test_name must not be empty")
        with self._locked():
            if self._active_run_locked() is not None:
                raise RuntimeError("A benchmark run is already active")
            run_id = str(uuid.uuid4())
            battery = initial_snapshot.get("battery")
            run = {
                "schema_version": 1,
                "run_id": run_id,
                "state": "running",
                "start_timestamp": start_timestamp,
                "end_timestamp": None,
                "test_name": chosen_test_name,
                "description": description or workload["description"],
                "workload": {
                    **workload,
                    "start_timestamp": start_timestamp if workload_name == "idle" else None,
                    "end_timestamp": None,
                },
                "initial_battery_state": battery,
                "final_battery_state": None,
                "telemetry_samples": [initial_snapshot],
                "configuration": {
                    "telemetry_schema_version": initial_snapshot.get("schema_version"),
                    "telemetry_interval_seconds": interval_seconds,
                },
                "environment": collect_environment(initial_snapshot),
                "data_errors": [],
            }
            self._write_json(self.runs_directory / f"{run_id}.json", run)
            self._write_json(self.active_path, {"run_id": run_id})
            return run

    def mark_workload_start(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        timestamp = _timestamp(snapshot)
        with self._locked():
            run = self._active_run_locked()
            if run is None or run.get("state") != "running":
                raise RuntimeError("No benchmark run is active")
            workload = run.get("workload")
            if not isinstance(workload, dict):
                raise ValueError("Benchmark workload metadata is invalid")
            if workload.get("start_timestamp") is not None:
                raise RuntimeError("Workload has already started")
            workload["start_timestamp"] = timestamp
            run["workload"] = workload
            samples = run.get("telemetry_samples")
            run["telemetry_samples"] = samples if isinstance(samples, list) else []
            run["telemetry_samples"].append(snapshot)
            self._write_json(self.runs_directory / f"{run['run_id']}.json", run)
            return run

    def mark_workload_stop(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        timestamp = _timestamp(snapshot)
        with self._locked():
            run = self._active_run_locked()
            if run is None or run.get("state") != "running":
                raise RuntimeError("No benchmark run is active")
            workload = run.get("workload")
            if not isinstance(workload, dict) or workload.get("start_timestamp") is None:
                raise RuntimeError("Workload has not been marked as started")
            if workload.get("end_timestamp") is not None:
                raise RuntimeError("Workload has already stopped")
            workload["end_timestamp"] = timestamp
            run["workload"] = workload
            samples = run.get("telemetry_samples")
            run["telemetry_samples"] = samples if isinstance(samples, list) else []
            run["telemetry_samples"].append(snapshot)
            self._write_json(self.runs_directory / f"{run['run_id']}.json", run)
            return run

    def append_sample(self, sample: dict[str, Any]) -> bool:
        if not isinstance(sample, dict) or not isinstance(sample.get("timestamp"), str):
            return False
        with self._locked():
            run = self._active_run_locked()
            if run is None or run.get("state") != "running":
                return False
            samples = run.get("telemetry_samples")
            if not isinstance(samples, list):
                samples = []
            samples.append(sample)
            run["telemetry_samples"] = samples
            self._write_json(self.runs_directory / f"{run['run_id']}.json", run)
            return True

    def stop(self, final_snapshot: dict[str, Any]) -> dict[str, Any] | None:
        if not isinstance(final_snapshot, dict):
            raise ValueError("final_snapshot must be an object")
        end_timestamp = _timestamp(final_snapshot)
        with self._locked():
            run = self._active_run_locked()
            if run is None:
                return None
            samples = run.get("telemetry_samples")
            if not isinstance(samples, list):
                samples = []
            samples.append(final_snapshot)
            run["telemetry_samples"] = samples
            run["end_timestamp"] = end_timestamp
            run["final_battery_state"] = final_snapshot.get("battery")
            run["state"] = "completed"
            workload = run.get("workload")
            if isinstance(workload, dict) and workload.get("execution") == "observe_only":
                workload["end_timestamp"] = end_timestamp
            self._write_json(self.runs_directory / f"{run['run_id']}.json", run)
            self.active_path.unlink(missing_ok=True)
            return run

    def active_run(self) -> dict[str, Any] | None:
        with self._locked():
            return self._active_run_locked()

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        try:
            validated_id = str(uuid.UUID(run_id))
        except (ValueError, AttributeError) as error:
            raise ValueError("run_id must be a UUID") from error
        with self._locked():
            return self._read_json(self.runs_directory / f"{validated_id}.json")

    def list_runs(self) -> list[dict[str, Any]]:
        with self._locked():
            try:
                paths = sorted(self.runs_directory.glob("*.json"))
            except OSError:
                return []
            runs = []
            for path in paths:
                try:
                    run = self._read_json(path)
                except ValueError:
                    continue
                if run is not None:
                    runs.append(run)
            return runs

    def latest_run(self) -> dict[str, Any] | None:
        runs = self.list_runs()
        return max(runs, key=lambda run: str(run.get("start_timestamp", "")), default=None)