import platform
from pathlib import Path
from typing import Any

from batteryos import __version__


def _cpu_model(cpuinfo_path: Path) -> str | None:
    try:
        for line in cpuinfo_path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            if separator and key.strip().casefold() in {"model name", "hardware", "processor"}:
                result = value.strip()
                if result:
                    return result
    except OSError:
        return platform.processor() or None
    return platform.processor() or None


def _memory_total_bytes(meminfo_path: Path) -> int | None:
    try:
        for line in meminfo_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                value_kib = int(line.split()[1])
                return value_kib * 1024
    except (OSError, ValueError, IndexError):
        return None
    return None


def collect_environment(
    initial_snapshot: dict[str, Any],
    *,
    cpuinfo_path: str | Path = "/proc/cpuinfo",
    meminfo_path: str | Path = "/proc/meminfo",
    platform_module: Any = platform,
) -> dict[str, Any]:
    battery = initial_snapshot.get("battery")
    devices = initial_snapshot.get("devices")
    battery = battery if isinstance(battery, dict) else {}
    devices = devices if isinstance(devices, dict) else {}
    return {
        "os_name": platform_module.system() or None,
        "os_release": platform_module.release() or None,
        "kernel_version": platform_module.version() or None,
        "architecture": platform_module.machine() or None,
        "cpu_model": _cpu_model(Path(cpuinfo_path)),
        "memory_total_bytes": _memory_total_bytes(Path(meminfo_path)),
        "battery_design_energy_wh_at_start": battery.get("energy_design_wh"),
        "battery_full_energy_wh_at_start": battery.get("energy_full_wh"),
        "screen_brightness_percent_at_start": devices.get("backlight_percent"),
        "ac_connected_at_start": battery.get("ac_connected"),
        "network_state_at_start": devices.get("wifi_connected"),
        "batteryos_version": __version__,
    }