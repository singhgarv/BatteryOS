import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from batteryos.simulation.runner import (
    format_result,
    run_all,
    run_scenario,
    scenarios,
)


class PolicySimulationRunnerTests(unittest.TestCase):
    @staticmethod
    def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
        repository_root = Path(__file__).resolve().parents[1]
        script = repository_root / "scripts" / "run_policy_simulation.py"
        environment = {**os.environ, "PYTHONPATH": str(repository_root / "src")}
        return subprocess.run(
            [sys.executable, str(script), *arguments],
            check=False,
            capture_output=True,
            text=True,
            cwd=repository_root,
            env=environment,
        )

    def test_covers_all_five_deterministic_scenarios(self) -> None:
        self.assertEqual(
            [scenario.name for scenario in scenarios()],
            ["low-battery", "high-cpu", "high-temperature", "ac-connected", "missing-telemetry"],
        )
        self.assertEqual(len(run_all()), 5)

    def test_scenario_outputs_include_recommendations_reasons_and_unavailable_inputs(self) -> None:
        for run in run_all():
            result = run["result"]
            self.assertIn("recommendations", result)
            self.assertIn("reasons", result)
            self.assertIn("unavailable_inputs", result)
            self.assertTrue(result["simulation_only"])

    def test_scenario_snapshots_are_isolated(self) -> None:
        first = run_scenario("low-battery")
        first["input_snapshot"]["battery"]["battery_level"] = 99

        second = run_scenario("low-battery")

        self.assertEqual(second["input_snapshot"]["battery"]["battery_level"], 10)

    def test_results_are_deterministic_and_json_serializable(self) -> None:
        first = run_all()
        second = run_all()

        self.assertEqual(first, second)
        json.dumps(first, sort_keys=True)

    def test_invalid_scenario_name_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown simulation scenario"):
            run_scenario("not-a-scenario")

    def test_missing_telemetry_is_reported(self) -> None:
        result = run_scenario("missing-telemetry")["result"]

        self.assertEqual(result["recommendations"], ["hypothetical_conservative_default"])
        self.assertIn("battery_percent", result["unavailable_inputs"])
        self.assertIn("temperature_c", result["unavailable_inputs"])

    def test_readable_format_displays_required_sections(self) -> None:
        output = format_result(run_scenario("high-cpu"))

        self.assertIn("Recommendations:", output)
        self.assertIn("Reasons:", output)
        self.assertIn("Unavailable inputs:", output)
        self.assertIn("Simulation only: yes", output)

    def test_runner_only_calls_simulator_with_synthetic_input(self) -> None:
        with patch("batteryos.simulation.runner.simulate_policy", return_value={
            "recommendations": [],
            "reasons": [],
            "unavailable_inputs": [],
        }) as simulator:
            run_scenario("ac-connected")

        simulator.assert_called_once()
        supplied_snapshot = simulator.call_args.args[0]
        self.assertEqual(supplied_snapshot["battery"]["ac_connected"], True)

    def test_cli_readable_output_contains_scenario_sections(self) -> None:
        result = self.run_cli()

        self.assertEqual(result.returncode, 0)
        self.assertIn("Scenario: low-battery", result.stdout)
        self.assertIn("Recommendations:", result.stdout)
        self.assertIn("Unavailable inputs:", result.stdout)

    def test_cli_json_output_contains_all_five_scenarios(self) -> None:
        result = self.run_cli("--json")

        self.assertEqual(result.returncode, 0)
        scenarios = json.loads(result.stdout)
        self.assertEqual(
            [scenario["scenario"] for scenario in scenarios],
            ["low-battery", "high-cpu", "high-temperature", "ac-connected", "missing-telemetry"],
        )

    def test_cli_json_output_can_select_one_scenario(self) -> None:
        result = self.run_cli("--scenario", "low-battery", "--json")

        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)[0]["scenario"], "low-battery")

    def test_cli_invalid_scenario_exits_nonzero(self) -> None:
        result = self.run_cli("--scenario", "not-a-scenario")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
