import argparse

from batteryos.benchmark.store import BenchmarkStore
from batteryos.daemon.service import BatteryDaemon
from batteryos.logging.events import EventLogger
from batteryos.telemetry.collector import TelemetryCollector


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect read-only BatteryOS telemetry.")
    parser.add_argument("--interval", type=float, default=10.0, help="Sampling interval in seconds")
    parser.add_argument("--once", action="store_true", help="Collect one sample and exit")
    parser.add_argument("--log-file", help="JSONL event log path (default: user state directory)")
    parser.add_argument(
        "--benchmark-directory",
        help="Benchmark run directory (default: user state directory)",
    )
    arguments = parser.parse_args()

    daemon = BatteryDaemon(
        collector=TelemetryCollector(),
        logger=EventLogger(arguments.log_file),
        benchmark_store=BenchmarkStore(arguments.benchmark_directory),
        interval_seconds=arguments.interval,
    )
    try:
        daemon.run(once=arguments.once)
    except KeyboardInterrupt:
        daemon.stop()


if __name__ == "__main__":
    main()