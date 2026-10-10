import argparse
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
for import_root in (REPOSITORY_ROOT, SOURCE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from batteryos.telemetry.collector import TelemetryCollector
from sensors.battery import BatterySensor
from sensors.telemetry import CpuUsageSensor, WifiSensor
from settings.backlight import BacklightController
from thermal.monitor import ThermalMonitor


POWER_SUPPLY_ATTRIBUTES = (
    "status",
    "online",
    "capacity",
    "energy_now",
    "energy_full",
    "energy_full_design",
    "charge_now",
    "charge_full",
    "charge_full_design",
    "voltage_now",
    "current_now",
    "power_now",
)
CPU_FREQUENCY_ATTRIBUTES = (
    "scaling_cur_freq",
    "cpuinfo_cur_freq",
    "scaling_min_freq",
    "scaling_max_freq",
    "scaling_available_frequencies",
    "cpuinfo_min_freq",
    "cpuinfo_max_freq",
)
BACKLIGHT_ATTRIBUTES = ("brightness", "actual_brightness", "max_brightness")


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None


def _read_optional_files(directory: Path, attributes: tuple[str, ...]) -> dict[str, str | None]:
    return {name: _read_text(directory / name) for name in attributes}


def _power_supplies(root: Path) -> list[dict[str, Any]] | None:
    try:
        paths = sorted(root.iterdir())
    except OSError:
        return None
    supplies = []
    for path in paths:
        supply_type = _read_text(path / "type")
        if supply_type is None:
            continue
        supplies.append(
            {
                "name": path.name,
                "type": supply_type,
                "attributes": _read_optional_files(path, POWER_SUPPLY_ATTRIBUTES),
            }
        )
    return supplies


def _cpu_info(
    cpuinfo_path: Path,
    proc_stat_path: Path,
    loadavg_path: Path,
    cpu_root: Path,
) -> dict[str, Any]:
    model_names = []
    processor_count = 0
    cpu_mhz_values = []
    try:
        for line in cpuinfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            key, value = key.strip().casefold(), value.strip()
            if key == "model name" and value:
                model_names.append(value)
            elif key == "processor":
                processor_count += 1
            elif key == "cpu mhz":
                try:
                    cpu_mhz_values.append(float(value))
                except ValueError:
                    pass
    except OSError:
        pass

    try:
        cpu_lines = [
            line
            for line in proc_stat_path.read_text(encoding="utf-8").splitlines()
            if line.split() and (
                line.split()[0] == "cpu"
                or line.split()[0].startswith("cpu") and line.split()[0][3:].isdigit()
            )
        ]
    except (OSError, IndexError):
        cpu_lines = []

    frequency_policies = []
    try:
        policies = sorted(
            set(
                list(cpu_root.glob("cpufreq"))
                + list(cpu_root.glob("policy*"))
                + list(cpu_root.glob("cpu[0-9]*/cpufreq"))
            )
        )
        for policy in policies:
            frequency_policies.append(
                {"path": str(policy), "attributes": _read_optional_files(policy, CPU_FREQUENCY_ATTRIBUTES)}
            )
    except OSError:
        pass

    return {
        "cpu_models": sorted(set(model_names)),
        "processor_entries": processor_count,
        "cpu_mhz_entries": cpu_mhz_values,
        "proc_stat_cpu_lines": cpu_lines,
        "loadavg_raw": _read_text(loadavg_path),
        "frequency_policies": frequency_policies,
    }


def _thermal_inventory(thermal_root: Path, hwmon_root: Path) -> dict[str, Any] | None:
    try:
        zones = sorted(thermal_root.glob("thermal_zone*"))
        devices = sorted(hwmon_root.glob("hwmon*"))
    except OSError:
        return None

    zone_entries = []
    for zone in zones:
        raw = _read_text(zone / "temp")
        zone_entries.append(
            {
                "name": _read_text(zone / "type") or zone.name,
                "path": str(zone / "temp"),
                "temperature_raw": raw,
                "temperature_c": ThermalMonitor._read_temperature(zone / "temp"),
            }
        )

    hwmon_entries = []
    for device in devices:
        device_name = _read_text(device / "name") or device.name
        for input_path in sorted(device.glob("temp*_input")):
            index = input_path.stem.removesuffix("_input")
            raw = _read_text(input_path)
            hwmon_entries.append(
                {
                    "device": device_name,
                    "label": _read_text(device / f"{index}_label"),
                    "path": str(input_path),
                    "temperature_raw": raw,
                    "temperature_c": ThermalMonitor._read_temperature(input_path),
                }
            )
    return {"thermal_zones": zone_entries, "hwmon_temperatures": hwmon_entries}


def _backlights(root: Path) -> list[dict[str, Any]] | None:
    try:
        devices = sorted(root.iterdir())
    except OSError:
        return None
    return [
        {
            "name": device.name,
            "path": str(device),
            "attributes": _read_optional_files(device, BACKLIGHT_ATTRIBUTES),
        }
        for device in devices
    ]


def _wireless_interfaces(root: Path) -> list[dict[str, Any]] | None:
    try:
        interfaces = sorted(root.iterdir())
    except OSError:
        return None
    return [
        {
            "name": interface.name,
            "operstate": _read_text(interface / "operstate"),
            "carrier": _read_text(interface / "carrier"),
        }
        for interface in interfaces
        if (interface / "wireless").exists()
    ]


def inspect_linux_interfaces(
    *,
    power_supply_root: str | Path = "/sys/class/power_supply",
    proc_stat_path: str | Path = "/proc/stat",
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    loadavg_path: str | Path = "/proc/loadavg",
    cpu_root: str | Path = "/sys/devices/system/cpu",
    thermal_root: str | Path = "/sys/class/thermal",
    hwmon_root: str | Path = "/sys/class/hwmon",
    backlight_root: str | Path = "/sys/class/backlight",
    network_root: str | Path = "/sys/class/net",
    system_name: str | None = None,
    profile_reader: Callable[[], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    actual_system = system_name or platform.system()
    if actual_system != "Linux":
        return {
            "schema_version": 1,
            "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "supported": False,
            "reason": "Linux hardware interface inventory requires Linux.",
        }

    battery_sensor = BatterySensor(power_supply_path=power_supply_root)
    cpu_sensor = CpuUsageSensor(proc_stat_path, loadavg_path, cpu_root)
    thermal_sensor = ThermalMonitor(thermal_root, hwmon_root)
    wifi_sensor = WifiSensor(network_root)
    backlight_sensor = BacklightController(backlight_root)
    collector = TelemetryCollector(
        battery=battery_sensor,
        cpu=cpu_sensor,
        thermal=thermal_sensor,
        wifi=wifi_sensor,
        backlight=backlight_sensor,
        profile_reader=profile_reader,
    )

    return {
        "schema_version": 1,
        "captured_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "supported": True,
        "platform": {
            "os_name": platform.system(),
            "os_release": platform.release(),
            "kernel_version": platform.version(),
            "architecture": platform.machine(),
        },
        "interfaces": {
            "power_supplies": _power_supplies(Path(power_supply_root)),
            "cpu": _cpu_info(
                Path(cpuinfo_path), Path(proc_stat_path), Path(loadavg_path), Path(cpu_root)
            ),
            "thermal": _thermal_inventory(Path(thermal_root), Path(hwmon_root)),
            "backlights": _backlights(Path(backlight_root)),
            "wireless_interfaces": _wireless_interfaces(Path(network_root)),
        },
        "batteryos_snapshot": collector.collect(),
        "safety": "Read-only inventory; no power settings or sysfs values are changed.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only Linux BatteryOS hardware inventory.")
    parser.add_argument("--output", help="Optional report file; refuses to overwrite an existing file")
    arguments = parser.parse_args()
    report = inspect_linux_interfaces()
    output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        output_path = Path(arguments.output)
        with output_path.open("x", encoding="utf-8", newline="\n") as report_file:
            report_file.write(output)
    else:
        print(output, end="")


if __name__ == "__main__":
    main()