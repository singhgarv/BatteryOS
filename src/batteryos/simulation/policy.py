import math
from typing import Any


SCHEMA_VERSION = 1
LOW_BATTERY_PERCENT = 20.0
CRITICAL_BATTERY_PERCENT = 10.0
HIGH_CPU_PERCENT = 80.0
HIGH_TEMPERATURE_C = 85.0
MIN_PLAUSIBLE_TEMPERATURE_C = -40.0
MAX_PLAUSIBLE_TEMPERATURE_C = 125.0


def _section(snapshot: Any, name: str) -> dict[str, Any]:
    if not isinstance(snapshot, dict):
        return {}
    value = snapshot.get(name)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _percentage(value: Any) -> float | None:
    number = _number(value)
    return number if number is not None and 0 <= number <= 100 else None


def _plausible_temperature(value: Any) -> float | None:
    number = _number(value)
    return (
        number
        if number is not None
        and MIN_PLAUSIBLE_TEMPERATURE_C <= number <= MAX_PLAUSIBLE_TEMPERATURE_C
        else None
    )


def _temperature(snapshot: dict[str, Any]) -> float | None:
    thermal = _section(snapshot, "thermal")
    hottest = _plausible_temperature(thermal.get("hottest_temperature_c"))
    if hottest is not None:
        return hottest
    zones = thermal.get("zones")
    if not isinstance(zones, list):
        return None
    values = [
        value
        for value in (_plausible_temperature(zone.get("temperature_c")) for zone in zones if isinstance(zone, dict))
        if value is not None
    ]
    return max(values) if values else None


def _observed_inputs(snapshot: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    battery = _section(snapshot, "battery")
    cpu = _section(snapshot, "cpu")
    devices = _section(snapshot, "devices")
    battery_percent = _percentage(battery.get("battery_level"))
    ac_connected = battery.get("ac_connected")
    if not isinstance(ac_connected, bool):
        ac_connected = None
    cpu_percent = _percentage(cpu.get("utilization_percent"))
    temperature_c = _temperature(snapshot)
    observed = {
        "battery_percent": battery_percent,
        "ac_connected": ac_connected,
        "cpu_utilization_percent": cpu_percent,
        "temperature_c": temperature_c,
        "wifi_connected": devices.get("wifi_connected") if isinstance(devices.get("wifi_connected"), bool) else None,
    }
    unavailable = [name for name, value in observed.items() if value is None]
    return observed, unavailable


def simulate_policy(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Evaluate hypothetical policy outcomes without reading or changing the host.

    Thresholds are intentionally explicit and deterministic:
    low battery <= 20%, critical battery <= 10%, high CPU >= 80%,
    and high temperature >= 85 C. Temperatures outside -40 C to 125 C,
    non-finite values, and percentages outside 0-100 are invalid. Missing or malformed values produce
    conservative recommendations and are listed in ``unavailable_inputs``.
    """
    if not isinstance(snapshot, dict):
        snapshot = {}
    observed, unavailable = _observed_inputs(snapshot)
    battery = observed["battery_percent"]
    ac_connected = observed["ac_connected"]
    cpu = observed["cpu_utilization_percent"]
    temperature = observed["temperature_c"]

    recommendations: list[str] = []
    reasons: list[str] = []
    if battery is not None and battery <= CRITICAL_BATTERY_PERCENT:
        recommendations.append("hypothetical_battery_saver")
        reasons.append(f"battery_percent <= {CRITICAL_BATTERY_PERCENT:g}")
    elif battery is not None and battery <= LOW_BATTERY_PERCENT:
        recommendations.append("hypothetical_battery_saver")
        reasons.append(f"battery_percent <= {LOW_BATTERY_PERCENT:g}")
    if temperature is not None and temperature >= HIGH_TEMPERATURE_C:
        recommendations.append("hypothetical_thermal_caution")
        reasons.append(f"temperature_c >= {HIGH_TEMPERATURE_C:g}")
    if cpu is not None and cpu >= HIGH_CPU_PERCENT:
        recommendations.append("hypothetical_reduce_background_work")
        reasons.append(f"cpu_utilization_percent >= {HIGH_CPU_PERCENT:g}")
    if ac_connected is True and not recommendations:
        recommendations.append("hypothetical_balanced_on_ac")
        reasons.append("ac_connected is true and no caution threshold was reached")
    if ac_connected is False and not recommendations:
        recommendations.append("hypothetical_balanced_on_battery")
        reasons.append("ac_connected is false and no caution threshold was reached")
    if not recommendations:
        recommendations.append("hypothetical_conservative_default")
        reasons.append("required decision inputs are unavailable")
    if unavailable:
        reasons.append("missing or malformed inputs were treated conservatively")

    return {
        "schema_version": SCHEMA_VERSION,
        "simulation_only": True,
        "observed_inputs": observed,
        "recommendations": recommendations,
        "reasons": reasons,
        "unavailable_inputs": unavailable,
        "thresholds": {
            "low_battery_percent": LOW_BATTERY_PERCENT,
            "critical_battery_percent": CRITICAL_BATTERY_PERCENT,
            "high_cpu_percent": HIGH_CPU_PERCENT,
            "high_temperature_c": HIGH_TEMPERATURE_C,
        },
        "measurement_claim": "No energy savings, runtime extension, or hardware change is measured or claimed.",
    }