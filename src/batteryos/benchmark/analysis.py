from datetime import datetime
from statistics import fmean
from typing import Any


METRIC_NAMES = (
    "battery_percent",
    "energy_remaining_wh",
    "energy_full_wh",
    "voltage_v",
    "current_a",
    "power_w",
    "cpu_utilization_percent",
    "cpu_frequency_khz",
    "load_average_1m",
    "temperature_c",
    "wifi_connected",
    "backlight_percent",
    "ac_connected",
)


def _section(sample: Any, name: str) -> dict[str, Any]:
    if not isinstance(sample, dict):
        return {}
    value = sample.get(name)
    return value if isinstance(value, dict) else {}


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _battery_values(sample: Any, field: str) -> list[float]:
    battery = _section(sample, "battery")
    batteries = battery.get("batteries")
    if isinstance(batteries, list):
        values = [_number(item.get(field)) for item in batteries if isinstance(item, dict)]
        return [value for value in values if value is not None]
    value = _number(battery.get(field))
    return [value] if value is not None else []


def _temperature_values(sample: Any) -> list[float]:
    thermal = _section(sample, "thermal")
    zones = thermal.get("zones")
    if isinstance(zones, list):
        values = [_number(zone.get("temperature_c")) for zone in zones if isinstance(zone, dict)]
        return [value for value in values if value is not None]
    value = _number(thermal.get("hottest_temperature_c"))
    return [value] if value is not None else []


def _sample_metric_values(sample: Any) -> dict[str, Any]:
    battery = _section(sample, "battery")
    cpu = _section(sample, "cpu")
    devices = _section(sample, "devices")
    frequency = cpu.get("frequency") if isinstance(cpu.get("frequency"), dict) else {}
    load_average = cpu.get("load_average") if isinstance(cpu.get("load_average"), dict) else {}
    voltages = _battery_values(sample, "voltage_v")
    currents = _battery_values(sample, "current_a")
    powers = _battery_values(sample, "power_w")
    temperatures = _temperature_values(sample)
    return {
        "battery_percent": _number(battery.get("battery_level")),
        "energy_remaining_wh": _number(battery.get("energy_now_wh")),
        "energy_full_wh": _number(battery.get("energy_full_wh")),
        "voltage_v": fmean(voltages) if voltages else None,
        "current_a": fmean(currents) if currents else None,
        "power_w": fmean(powers) if powers else None,
        "cpu_utilization_percent": _number(cpu.get("utilization_percent")),
        "cpu_frequency_khz": _number(frequency.get("current_khz")),
        "load_average_1m": _number(load_average.get("1m")),
        "temperature_c": fmean(temperatures) if temperatures else None,
        "wifi_connected": devices.get("wifi_connected") if isinstance(devices.get("wifi_connected"), bool) else None,
        "backlight_percent": _number(devices.get("backlight_percent")),
        "ac_connected": battery.get("ac_connected") if isinstance(battery.get("ac_connected"), bool) else None,
    }


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed


def _battery_provenance(battery: Any, field: str) -> str | None:
    if not isinstance(battery, dict):
        return None
    provenance = battery.get("measurement_provenance")
    if isinstance(provenance, dict):
        value = provenance.get(field)
        if isinstance(value, str):
            return value
    batteries = battery.get("batteries")
    if isinstance(batteries, list):
        values = []
        for item in batteries:
            if isinstance(item, dict) and _number(item.get(field)) is not None:
                item_provenance = item.get("measurement_provenance")
                if isinstance(item_provenance, dict):
                    classification = item_provenance.get(field)
                    if isinstance(classification, str):
                        values.append(classification)
        if values:
            return values[0] if len(set(values)) == 1 else "mixed"
    return None


def _provenance_pair(initial: Any, final: Any, field: str) -> str:
    classifications = {
        value
        for value in (
            _battery_provenance(initial, field),
            _battery_provenance(final, field),
        )
        if value is not None
    }
    if len(classifications) == 1:
        return next(iter(classifications))
    if classifications:
        return "mixed"
    return "unknown"


def analyze_run(run: dict[str, Any]) -> dict[str, Any]:
    raw_samples = run.get("telemetry_samples")
    if isinstance(raw_samples, list):
        entries = raw_samples
    elif raw_samples is None:
        entries = []
    else:
        entries = [raw_samples]

    valid_samples = [
        sample
        for sample in entries
        if isinstance(sample, dict) and _parse_timestamp(sample.get("timestamp")) is not None
    ]
    invalid_sample_count = len(entries) - len(valid_samples)
    metric_rows = [_sample_metric_values(sample) for sample in valid_samples]
    parsed_timestamps = [_parse_timestamp(sample.get("timestamp")) for sample in valid_samples]
    timestamp_order_errors = sum(
        current < previous
        for previous, current in zip(parsed_timestamps, parsed_timestamps[1:])
        if previous is not None and current is not None
    )
    metric_slots = max(0, len(entries)) * len(METRIC_NAMES)
    missing_slots = invalid_sample_count * len(METRIC_NAMES)
    for row in metric_rows:
        missing_slots += sum(row[name] is None for name in METRIC_NAMES)
    missing_percentage = (missing_slots * 100 / metric_slots) if metric_slots else None

    initial_battery = run.get("initial_battery_state")
    final_battery = run.get("final_battery_state")
    if not isinstance(initial_battery, dict) and valid_samples:
        initial_battery = _section(valid_samples[0], "battery")
    if not isinstance(final_battery, dict) and valid_samples:
        final_battery = _section(valid_samples[-1], "battery")
    initial_battery = initial_battery if isinstance(initial_battery, dict) else {}
    final_battery = final_battery if isinstance(final_battery, dict) else {}

    initial_percent = _number(initial_battery.get("battery_level"))
    final_percent = _number(final_battery.get("battery_level"))
    initial_energy = _number(initial_battery.get("energy_now_wh"))
    final_energy = _number(final_battery.get("energy_now_wh"))
    percent_change = (
        round(final_percent - initial_percent, 3)
        if initial_percent is not None and final_percent is not None
        else None
    )
    energy_change = (
        round(final_energy - initial_energy, 6)
        if initial_energy is not None and final_energy is not None
        else None
    )

    start = _parse_timestamp(run.get("start_timestamp"))
    end = _parse_timestamp(run.get("end_timestamp"))
    if end is None and valid_samples:
        end = _parse_timestamp(valid_samples[-1].get("timestamp"))
    duration_seconds = max(0.0, (end - start).total_seconds()) if start and end else None
    workload = run.get("workload")
    workload = workload if isinstance(workload, dict) else {}
    workload_start = _parse_timestamp(workload.get("start_timestamp"))
    workload_end = _parse_timestamp(workload.get("end_timestamp"))
    workload_duration = (
        max(0.0, (workload_end - workload_start).total_seconds())
        if workload_start and workload_end
        else None
    )

    cpu_values = [row["cpu_utilization_percent"] for row in metric_rows if row["cpu_utilization_percent"] is not None]
    temperature_values = [row["temperature_c"] for row in metric_rows if row["temperature_c"] is not None]
    power_values: list[float] = []
    power_provenance: set[str] = set()
    for sample in valid_samples:
        battery = _section(sample, "battery")
        batteries = battery.get("batteries")
        if isinstance(batteries, list):
            for item in batteries:
                if not isinstance(item, dict):
                    continue
                if str(item.get("status", "")).casefold() != "discharging":
                    continue
                value = _number(item.get("power_w"))
                if value is None:
                    continue
                power_values.append(value)
                item_provenance = item.get("measurement_provenance")
                classification = item_provenance.get("power_w") if isinstance(item_provenance, dict) else None
                power_provenance.add(classification if isinstance(classification, str) else "unknown")
        else:
            value = _number(battery.get("power_w"))
            if value is not None:
                power_values.append(value)
                classification = _battery_provenance(battery, "power_w")
                power_provenance.add(classification or "unknown")

    average_power = None
    if power_values:
        average_power = {
            "value_w": round(fmean(power_values), 6),
            "method": "mean of observed battery power samples",
            "value_class": next(iter(power_provenance)) if len(power_provenance) == 1 else "mixed",
            "sample_count": len(power_values),
        }
    elif (
        energy_change is not None
        and energy_change < 0
        and duration_seconds
        and duration_seconds > 0
        and valid_samples
        and all(
            _section(sample, "battery").get("ac_connected") is False
            and _section(sample, "battery").get("charging") is False
            for sample in valid_samples
        )
    ):
        average_power = {
            "value_w": round(-energy_change / (duration_seconds / 3600), 6),
            "method": "energy delta divided by elapsed time",
            "value_class": "calculated_estimate",
            "sample_count": 2,
        }

    return {
        "schema_version": 1,
        "run_id": run.get("run_id"),
        "test_name": run.get("test_name"),
        "state": run.get("state"),
        "start_timestamp": run.get("start_timestamp"),
        "end_timestamp": run.get("end_timestamp"),
        "duration_seconds": round(duration_seconds, 3) if duration_seconds is not None else None,
        "workload_duration_seconds": round(workload_duration, 3) if workload_duration is not None else None,
        "sample_count": len(valid_samples),
        "invalid_sample_count": invalid_sample_count,
        "timestamps_monotonic": timestamp_order_errors == 0 if valid_samples else None,
        "timestamp_order_errors": timestamp_order_errors,
        "battery_percentage_point_change": percent_change,
        "battery_percentage_change_class": "calculated_from_kernel_reported_percentages" if percent_change is not None else "unavailable",
        "energy_remaining_change_wh": energy_change,
        "energy_change_class": _provenance_pair(initial_battery, final_battery, "energy_now_wh"),
        "average_power": average_power,
        "average_cpu_utilization_percent": round(fmean(cpu_values), 3) if cpu_values else None,
        "cpu_utilization_class": "calculated_from_kernel_counters" if cpu_values else "unavailable",
        "average_temperature_c": round(fmean(temperature_values), 3) if temperature_values else None,
        "temperature_class": "kernel_reported" if temperature_values else "unavailable",
        "missing_metric_count": missing_slots,
        "metric_slot_count": metric_slots,
        "missing_data_percentage": round(missing_percentage, 3) if missing_percentage is not None else None,
        "missing_data_denominator": list(METRIC_NAMES),
        "description": run.get("description"),
        "workload": run.get("workload"),
        "configuration": run.get("configuration"),
        "environment": run.get("environment"),
    }