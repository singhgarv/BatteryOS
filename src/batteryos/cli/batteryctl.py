import argparse
import json
from typing import Any

from batteryos.benchmark.analysis import analyze_run
from batteryos.benchmark.store import BenchmarkStore
from batteryos.hardware.profile import read_current_profile
from batteryos.logging.events import EventLogger
from batteryos.telemetry.collector import TelemetryCollector


def _json_output(value: Any) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def _latest_snapshot(logger: EventLogger) -> dict | None:
    for event in reversed(logger.read(limit=1000)):
        if event.get("event_type") == "telemetry.sample":
            snapshot = event.get("data", {}).get("snapshot")
            if isinstance(snapshot, dict):
                return snapshot
    return None


def _stats(logger: EventLogger) -> dict[str, Any]:
    events = logger.read(limit=100_000)
    samples = [
        event.get("data", {}).get("snapshot", {})
        for event in events
        if event.get("event_type") == "telemetry.sample"
    ]
    samples = [sample for sample in samples if isinstance(sample, dict)]
    levels = [
        sample.get("battery", {}).get("battery_level")
        for sample in samples
        if isinstance(sample.get("battery"), dict)
    ]
    levels = [level for level in levels if isinstance(level, (int, float))]
    first_level = levels[0] if levels else None
    last_level = levels[-1] if levels else None
    return {
        "sample_count": len(samples),
        "error_event_count": sum(event.get("event_type") == "telemetry.error" for event in events),
        "first_sample_timestamp": samples[0].get("timestamp") if samples else None,
        "last_sample_timestamp": samples[-1].get("timestamp") if samples else None,
        "first_battery_percent": first_level,
        "last_battery_percent": last_level,
        "observed_battery_percentage_point_change": (
            round(last_level - first_level, 2)
            if first_level is not None and last_level is not None
            else None
        ),
        "note": "Descriptive telemetry only; not a runtime or battery-life benchmark.",
    }


def _benchmark_command(arguments: argparse.Namespace, logger: EventLogger) -> None:
    store = BenchmarkStore(arguments.benchmark_directory)
    action = arguments.benchmark_action
    if action == "list":
        runs = store.list_runs()
        _json_output(
            [
                {
                    "run_id": run.get("run_id"),
                    "state": run.get("state"),
                    "test_name": run.get("test_name"),
                    "start_timestamp": run.get("start_timestamp"),
                    "end_timestamp": run.get("end_timestamp"),
                }
                for run in runs
            ]
        )
        return

    if action == "start":
        snapshot = TelemetryCollector().collect()
        try:
            run = store.start(
                snapshot,
                workload_name=arguments.workload,
                test_name=arguments.test_name,
                description=arguments.description,
                interval_seconds=arguments.interval_seconds,
            )
        except (RuntimeError, ValueError) as error:
            _json_output({"error": str(error)})
            return
        logger.write(
            "benchmark.started",
            {"run_id": run["run_id"], "workload": run["workload"], "test_name": run["test_name"]},
            timestamp=run["start_timestamp"],
        )
        _json_output(
            {
                "run_id": run["run_id"],
                "state": run["state"],
                "start_timestamp": run["start_timestamp"],
                "message": "Run started. Keep battery-d running to collect periodic samples; no workload is launched.",
            }
        )
        return

    if action == "status":
        run = store.active_run()
        if run is None:
            _json_output({"state": "idle", "message": "No benchmark run is active."})
        else:
            _json_output(
                {
                    "run_id": run.get("run_id"),
                    "state": run.get("state"),
                    "test_name": run.get("test_name"),
                    "start_timestamp": run.get("start_timestamp"),
                    "sample_count": len(run.get("telemetry_samples", []))
                    if isinstance(run.get("telemetry_samples"), list)
                    else 0,
                }
            )
        return

    if action in {"workload-start", "workload-stop"}:
        snapshot = TelemetryCollector().collect()
        try:
            run = (
                store.mark_workload_start(snapshot)
                if action == "workload-start"
                else store.mark_workload_stop(snapshot)
            )
        except (RuntimeError, ValueError) as error:
            _json_output({"error": str(error)})
            return
        logger.write(
            f"benchmark.{action}",
            {"run_id": run["run_id"], "workload": run["workload"]},
            timestamp=snapshot["timestamp"],
        )
        _json_output({"run_id": run["run_id"], "workload": run["workload"]})
        return

    if action == "stop":
        final_snapshot = TelemetryCollector().collect()
        run = store.stop(final_snapshot)
        if run is None:
            _json_output({"state": "idle", "message": "No benchmark run is active."})
            return
        logger.write(
            "benchmark.completed",
            {"run_id": run["run_id"], "sample_count": len(run["telemetry_samples"])},
            timestamp=run["end_timestamp"],
        )
        _json_output(analyze_run(run))
        return

    if action == "report":
        try:
            run = store.get_run(arguments.run_id) if arguments.run_id else store.latest_run()
        except ValueError as error:
            _json_output({"error": str(error)})
            return
        if run is None:
            _json_output({"error": "No benchmark run was found."})
            return
        _json_output(analyze_run(run))
        return

    arguments_parser = arguments.parser
    arguments_parser.error("Use batteryctl benchmark list|start|status|stop|report")


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect read-only BatteryOS telemetry.")
    parser.add_argument(
        "command",
        choices=("status", "battery", "cpu", "thermal", "logs", "stats", "profile", "benchmark"),
    )
    parser.add_argument("benchmark_action", nargs="?")
    parser.add_argument("run_id", nargs="?")
    parser.add_argument("--log-file", help="JSONL event log path (default: user state directory)")
    parser.add_argument("--limit", type=int, default=20, help="Maximum log events to display")
    parser.add_argument("--refresh", action="store_true", help="Collect a fresh sample before displaying data")
    parser.add_argument("--workload", choices=("idle", "cpu-placeholder", "manual"), default="idle")
    parser.add_argument("--test-name")
    parser.add_argument("--description")
    parser.add_argument("--interval-seconds", type=float, default=10.0)
    parser.add_argument("--benchmark-directory")
    arguments = parser.parse_args()

    logger = EventLogger(arguments.log_file)
    if arguments.command == "benchmark":
        arguments.parser = parser
        if arguments.benchmark_action not in {
            "list", "start", "status", "workload-start", "workload-stop", "stop", "report"
        }:
            parser.error("benchmark requires list, start, status, workload-start, workload-stop, stop, or report")
        _benchmark_command(arguments, logger)
        return
    if arguments.command == "logs":
        if arguments.limit < 1:
            parser.error("--limit must be positive")
        _json_output(logger.read(arguments.limit))
        return
    if arguments.command == "stats":
        _json_output(_stats(logger))
        return
    if arguments.command == "profile":
        _json_output(read_current_profile())
        return

    snapshot = TelemetryCollector().collect() if arguments.refresh else _latest_snapshot(logger)
    if snapshot is None:
        print("No telemetry sample found. Run battery-d --once or use --refresh.")
        return

    if arguments.command == "status":
        _json_output(snapshot)
    elif arguments.command == "battery":
        _json_output(snapshot.get("battery"))
    elif arguments.command == "cpu":
        _json_output(snapshot.get("cpu"))
    elif arguments.command == "thermal":
        _json_output(snapshot.get("thermal"))


if __name__ == "__main__":
    main()