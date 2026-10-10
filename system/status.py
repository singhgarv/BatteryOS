from power.profile_manager import POWER_PROFILE_MANAGER
from sensors.charging import charging_state
from thermal.manager import THERMAL_MANAGER
from ui.stats import get_system_stats


def get_system_status() -> dict[str, int | bool | float | str | None]:
    stats = get_system_stats()
    battery = {
        key: stats[key]
        for key in (
            "battery_level",
            "battery_health",
            "charging",
            "estimated_runtime_hours",
        )
    }
    return {
        **battery,
        "state": "active",
        "power_mode": POWER_PROFILE_MANAGER.get_current_mode().name,
        "charging_text": charging_state(battery["charging"]),
        "cpu_load": stats["cpu_usage"],
        "wifi_connected": stats["wifi_connected"],
        "thermal_state": THERMAL_MANAGER.status_line(),
    }


def render_system_status() -> str:
    status = get_system_status()
    level = status["battery_level"]
    health = status["battery_health"]
    level_text = f"{level}%" if level is not None else "unknown"
    health_text = f"{health}%" if health is not None else "unknown"
    cpu_load = status["cpu_load"]
    cpu_text = f"{cpu_load}%" if cpu_load is not None else "unknown"
    wifi_connected = status["wifi_connected"]
    wifi_text = "connected" if wifi_connected is True else "disconnected" if wifi_connected is False else "unknown"
    return (
        f"System status: {status['state']}\n"
        f"Battery: {level_text}\n"
        f"Health: {health_text}\n"
        f"Charging: {status['charging_text']}\n"
        f"Mode: {status['power_mode']}\n"
        f"CPU load: {cpu_text}\n"
        f"Wi-Fi: {wifi_text}\n"
        f"Thermal state: {status['thermal_state']}"
    )