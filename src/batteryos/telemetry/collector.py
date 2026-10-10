from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from batteryos.hardware.profile import read_current_profile
from sensors.battery import BatterySensor
from sensors.telemetry import CpuUsageSensor, WifiSensor
from settings.backlight import BacklightController
from thermal.monitor import ThermalMonitor


class TelemetryCollector:
    """Collect one best-effort, read-only Linux telemetry snapshot."""

    def __init__(
        self,
        battery: Any | None = None,
        cpu: Any | None = None,
        thermal: Any | None = None,
        wifi: Any | None = None,
        backlight: Any | None = None,
        profile_reader: Callable[[], dict[str, Any]] | None = None,
        clock: Callable[[], datetime] | None = None,
    ):
        self.battery = battery or BatterySensor()
        self.cpu = cpu or CpuUsageSensor()
        self.thermal = thermal or ThermalMonitor()
        self.wifi = wifi or WifiSensor()
        self.backlight = backlight or BacklightController()
        self.profile_reader = profile_reader or read_current_profile
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _collect(source: str, operation: Callable[[], Any], errors: list[dict[str, str]]) -> Any:
        try:
            return operation()
        except Exception as error:
            errors.append({"source": source, "error": f"{type(error).__name__}: {error}"})
            return None

    def collect(self) -> dict[str, Any]:
        errors: list[dict[str, str]] = []
        battery = self._collect("battery", self.battery.get_status, errors)
        cpu = self._collect("cpu", self.cpu.read_telemetry, errors)
        thermal = self._collect("thermal", self.thermal.read_telemetry, errors)
        wifi = self._collect("wifi", self.wifi.is_connected, errors)
        backlight = self._collect("backlight", self.backlight.read_percent, errors)
        profile = self._collect("profile", self.profile_reader, errors)
        timestamp = self.clock()
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        return {
            "schema_version": 1,
            "timestamp": timestamp.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
            "battery": battery,
            "cpu": cpu,
            "thermal": thermal,
            "devices": {"wifi_connected": wifi, "backlight_percent": backlight},
            "power": profile,
            "errors": errors,
        }