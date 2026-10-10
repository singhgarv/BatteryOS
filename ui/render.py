from .stats import get_system_stats


def render_taskbar(stats: dict | None = None) -> str:
    if stats is None:
        stats = get_system_stats()

    health = stats.get("battery_health", 0)
    battery = stats.get("battery_level", 0)
    health_text = f"{health}%" if health is not None else "N/A"
    battery_text = f"{battery}%" if battery is not None else "N/A"
    charging = stats.get("charging")
    charging_text = "Charging" if charging is True else "Not charging" if charging is False else "Power unknown"
    power_mode = stats.get("power_mode", "Balanced")
    time_value = stats.get("time", "00:00")
    date_value = stats.get("date", "Mon, Jan 01")
    cpu_usage = stats.get("cpu_usage", 0)
    cpu_text = f"{cpu_usage}%" if cpu_usage is not None else "N/A"
    wifi_connected = stats.get("wifi_connected")
    wifi_state = "Connected" if wifi_connected is True else "Disconnected" if wifi_connected is False else "Unknown"

    return (
        f"[Health {health_text}] [Battery {battery_text}] [{charging_text}] [{power_mode}] "
        f"[{time_value}] [{date_value}] [CPU {cpu_text}] [Wi-Fi {wifi_state}]"
    )
