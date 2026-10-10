from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TemperatureReading:
    name: str
    celsius: float
    source: str


class ThermalMonitor:
    def __init__(
        self,
        thermal_root: str | Path = "/sys/class/thermal",
        hwmon_root: str | Path = "/sys/class/hwmon",
    ):
        self.thermal_root = Path(thermal_root)
        self.hwmon_root = Path(hwmon_root)

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    @classmethod
    def _read_temperature(cls, path: Path) -> float | None:
        raw_value = cls._read_text(path)
        if raw_value is None:
            return None
        try:
            temperature = float(raw_value)
        except ValueError:
            return None
        if abs(temperature) >= 1000:
            temperature /= 1000
        if not -40 <= temperature <= 150:
            return None
        return round(temperature, 1)

    def _read_thermal_zones(self) -> list[TemperatureReading]:
        readings = []
        try:
            zones = sorted(self.thermal_root.glob("thermal_zone*"))
        except OSError:
            return readings
        for zone in zones:
            name = self._read_text(zone / "type") or zone.name
            temperature = self._read_temperature(zone / "temp")
            if temperature is not None:
                readings.append(TemperatureReading(name, temperature, str(zone / "temp")))
        return readings

    def _read_hwmon(self) -> list[TemperatureReading]:
        readings = []
        try:
            devices = sorted(self.hwmon_root.glob("hwmon*"))
        except OSError:
            return readings
        for device in devices:
            chip_name = self._read_text(device / "name") or device.name
            for input_path in sorted(device.glob("temp*_input")):
                sensor_index = input_path.stem.removesuffix("_input")
                label = self._read_text(device / f"{sensor_index}_label") or ""
                name = " ".join(part for part in (chip_name, label) if part)
                temperature = self._read_temperature(input_path)
                if temperature is not None:
                    readings.append(TemperatureReading(name, temperature, str(input_path)))
        return readings

    def read_temperatures(self) -> list[TemperatureReading]:
        return self._read_thermal_zones() + self._read_hwmon()

    def read_telemetry(self) -> dict:
        readings = self.read_temperatures()
        return {
            "zones": [
                {
                    "name": reading.name,
                    "temperature_c": reading.celsius,
                    "source": reading.source,
                }
                for reading in readings
            ],
            "hottest_temperature_c": max(
                (reading.celsius for reading in readings), default=None
            ),
            "throttling": self.read_throttling(),
        }

    def read_throttling(self) -> dict[str, int] | None:
        try:
            paths = sorted(self.thermal_root.glob("cooling_device*/cur_state"))
        except OSError:
            return None
        states = {}
        for path in paths:
            try:
                states[path.parent.name] = int(path.read_text(encoding="utf-8").strip())
            except (OSError, ValueError):
                continue
        return states or None