from datetime import datetime

from power.profile_manager import POWER_PROFILE_MANAGER
from sensors.battery import BatterySensor
from sensors.telemetry import CpuUsageSensor, WifiSensor

CPU_USAGE_SENSOR = CpuUsageSensor()
WIFI_SENSOR = WifiSensor()


def get_system_stats() -> dict:
    now = datetime.now()
    battery = BatterySensor().get_status()
    return {
        **battery,
        "power_mode": POWER_PROFILE_MANAGER.get_current_mode().name.title(),
        "time": now.strftime("%I:%M %p"),
        "date": now.strftime("%a, %b %d"),
        "cpu_usage": CPU_USAGE_SENSOR.read_percent(),
        "wifi_connected": WIFI_SENSOR.is_connected(),
    }
