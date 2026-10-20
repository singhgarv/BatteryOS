"""Repeatable synthetic-input runner for the simulation-only policy."""

from copy import deepcopy
from dataclasses import dataclass
import json
from typing import Any

from .policy import simulate_policy


@dataclass(frozen=True)
class Scenario:
    name: str
    description: str
    _snapshot_json: str

    @property
    def snapshot(self) -> dict[str, Any]:
        """Return an isolated snapshot copy for this run."""
        value = json.loads(self._snapshot_json)
        return deepcopy(value)


_SCENARIO_DATA: tuple[tuple[str, str, dict[str, Any]], ...] = (
    (
        "low-battery",
        "Battery is low while running on battery power.",
        {
            "battery": {"battery_level": 10, "ac_connected": False},
            "cpu": {"utilization_percent": 20},
            "thermal": {"zones": [{"name": "CPU Package", "temperature_c": 50}]},
            "devices": {"wifi_connected": True},
        },
    ),
    (
        "high-cpu",
        "CPU utilization is high while other readings are nominal.",
        {
            "battery": {"battery_level": 70, "ac_connected": False},
            "cpu": {"utilization_percent": 90},
            "thermal": {"zones": [{"name": "CPU Package", "temperature_c": 55}]},
            "devices": {"wifi_connected": True},
        },
    ),
    (
        "high-temperature",
        "Reported CPU temperature is high.",
        {
            "battery": {"battery_level": 70, "ac_connected": False},
            "cpu": {"utilization_percent": 20},
            "thermal": {"zones": [{"name": "CPU Package", "temperature_c": 90}]},
            "devices": {"wifi_connected": True},
        },
    ),
    (
        "ac-connected",
        "AC power is connected and no caution threshold is reached.",
        {
            "battery": {"battery_level": 80, "ac_connected": True},
            "cpu": {"utilization_percent": 20},
            "thermal": {"zones": [{"name": "CPU Package", "temperature_c": 50}]},
            "devices": {"wifi_connected": True},
        },
    ),
    (
        "missing-telemetry",
        "Required decision telemetry is unavailable.",
        {},
    ),
)

SCENARIOS: tuple[Scenario, ...] = tuple(
    Scenario(name, description, json.dumps(snapshot, sort_keys=True, separators=(",", ":")))
    for name, description, snapshot in _SCENARIO_DATA
)
_SCENARIOS_BY_NAME = {scenario.name: scenario for scenario in SCENARIOS}


def scenarios() -> tuple[Scenario, ...]:
    """Return the immutable scenario definitions."""
    return SCENARIOS


def run_scenario(name: str) -> dict[str, Any]:
    """Run one named synthetic scenario through ``simulate_policy``."""
    try:
        scenario = _SCENARIOS_BY_NAME[name]
    except KeyError as error:
        raise ValueError(f"Unknown simulation scenario: {name}") from error
    input_snapshot = scenario.snapshot
    result = simulate_policy(input_snapshot)
    return {
        "scenario": scenario.name,
        "description": scenario.description,
        "input_snapshot": input_snapshot,
        "result": result,
    }


def run_all() -> list[dict[str, Any]]:
    """Run all scenarios in their stable definition order."""
    return [run_scenario(scenario.name) for scenario in SCENARIOS]


def format_result(run: dict[str, Any]) -> str:
    """Render one simulation result without adding claims or measurements."""
    result = run["result"]
    recommendations = result["recommendations"]
    reasons = result["reasons"]
    unavailable = result["unavailable_inputs"]
    unavailable_lines = [f"  - {input_name}" for input_name in unavailable]
    if not unavailable_lines:
        unavailable_lines = ["  - none"]
    return "\n".join(
        [
            f"Scenario: {run['scenario']}",
            f"Description: {run['description']}",
            "Recommendations:",
            *[f"  - {recommendation}" for recommendation in recommendations],
            "Reasons:",
            *[f"  - {reason}" for reason in reasons],
            "Unavailable inputs:",
            *unavailable_lines,
            "Simulation only: yes",
            "Measurement claim: no energy savings or runtime extension is measured or claimed.",
        ]
    )
