from sensors.battery import BatterySensor
from sensors.charging import charging_state
from sensors.health import battery_health_status


def show_battery_settings() -> str:
    status = BatterySensor().get_status()
    level = status["battery_level"]
    health = status["battery_health"]
    runtime = status["estimated_runtime_hours"]
    level_text = f"{level}%" if level is not None else "unknown"
    health_text = "unknown"
    if health is not None:
        health_text = f"{health}% ({battery_health_status(health)})"
    runtime_text = "unknown"
    if runtime is not None:
        minutes = round(runtime * 60)
        runtime_text = f"{minutes // 60}h {minutes % 60:02d}m"

    return (
        f"Battery level: {level_text}\n"
        f"Battery health: {health_text}\n"
        f"Charging: {charging_state(status['charging'])}\n"
        f"Estimated runtime: {runtime_text}"
    )