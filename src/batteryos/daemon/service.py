import time
from collections.abc import Callable

from batteryos.benchmark.store import BenchmarkStore
from batteryos.logging.events import EventLogger
from batteryos.telemetry.collector import TelemetryCollector


class BatteryDaemon:
    def __init__(
        self,
        collector: TelemetryCollector | None = None,
        logger: EventLogger | None = None,
        benchmark_store: BenchmarkStore | None = None,
        interval_seconds: float = 10.0,
        sleeper: Callable[[float], None] = time.sleep,
    ):
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        self.collector = collector or TelemetryCollector()
        self.logger = logger or EventLogger()
        self.benchmark_store = benchmark_store or BenchmarkStore()
        self.interval_seconds = interval_seconds
        self.sleeper = sleeper
        self.running = False

    def sample_once(self) -> dict:
        snapshot = self.collector.collect()
        self.logger.write(
            "telemetry.sample",
            {"snapshot": snapshot},
            timestamp=snapshot["timestamp"],
        )
        self.benchmark_store.append_sample(snapshot)
        for error in snapshot["errors"]:
            self.logger.write(
                "telemetry.error",
                error,
                timestamp=snapshot["timestamp"],
            )
        return snapshot

    def run(self, once: bool = False, max_samples: int | None = None) -> int:
        if max_samples is not None and max_samples < 1:
            raise ValueError("max_samples must be positive")
        self.running = True
        sample_count = 0
        while self.running:
            try:
                self.sample_once()
            except Exception as error:
                self.logger.write(
                    "daemon.error",
                    {"error": f"{type(error).__name__}: {error}"},
                )
            sample_count += 1
            if once or max_samples is not None and sample_count >= max_samples:
                break
            self.sleeper(self.interval_seconds)
        self.running = False
        return sample_count

    def stop(self) -> None:
        self.running = False