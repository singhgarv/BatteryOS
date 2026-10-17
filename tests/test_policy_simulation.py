import unittest
from math import inf, nan

from batteryos.simulation.policy import simulate_policy


def snapshot(
    *,
    battery: object = 80,
    ac: object = False,
    cpu: object = 20,
    temperature: object = 50,
) -> dict:
    return {
        "battery": {"battery_level": battery, "ac_connected": ac},
        "cpu": {"utilization_percent": cpu},
        "thermal": {"zones": [{"name": "CPU Package", "temperature_c": temperature}]},
        "devices": {"wifi_connected": True},
    }


class PolicySimulationTests(unittest.TestCase):
    def test_low_battery_recommends_hypothetical_saver(self) -> None:
        result = simulate_policy(snapshot(battery=10))

        self.assertTrue(result["simulation_only"])
        self.assertIn("hypothetical_battery_saver", result["recommendations"])
        self.assertIn("battery_percent <= 10", result["reasons"])

    def test_ac_operation_uses_balanced_hypothetical_recommendation(self) -> None:
        result = simulate_policy(snapshot(ac=True))

        self.assertEqual(result["recommendations"], ["hypothetical_balanced_on_ac"])

    def test_high_cpu_and_temperature_are_reported(self) -> None:
        result = simulate_policy(snapshot(cpu=90, temperature=90))

        self.assertIn("hypothetical_reduce_background_work", result["recommendations"])
        self.assertIn("hypothetical_thermal_caution", result["recommendations"])
        self.assertIn("cpu_utilization_percent >= 80", result["reasons"])
        self.assertIn("temperature_c >= 85", result["reasons"])

    def test_missing_telemetry_is_conservative_and_explicit(self) -> None:
        result = simulate_policy({})

        self.assertEqual(result["recommendations"], ["hypothetical_conservative_default"])
        self.assertEqual(
            result["unavailable_inputs"],
            ["battery_percent", "ac_connected", "cpu_utilization_percent", "temperature_c", "wifi_connected"],
        )

    def test_malformed_values_do_not_crash_or_become_fake_values(self) -> None:
        result = simulate_policy(snapshot(battery="10", ac="yes", cpu=[], temperature="hot"))

        self.assertTrue(result["simulation_only"])
        self.assertIsNone(result["observed_inputs"]["battery_percent"])
        self.assertIsNone(result["observed_inputs"]["ac_connected"])
        self.assertIn("battery_percent", result["unavailable_inputs"])
        self.assertIn("temperature_c", result["unavailable_inputs"])

    def test_negative_battery_percentage_is_unavailable(self) -> None:
        result = simulate_policy(snapshot(battery=-1))

        self.assertIsNone(result["observed_inputs"]["battery_percent"])
        self.assertIn("battery_percent", result["unavailable_inputs"])

    def test_battery_percentage_above_100_is_unavailable(self) -> None:
        result = simulate_policy(snapshot(battery=101))

        self.assertIsNone(result["observed_inputs"]["battery_percent"])
        self.assertIn("battery_percent", result["unavailable_inputs"])

    def test_cpu_above_100_is_unavailable(self) -> None:
        result = simulate_policy(snapshot(cpu=101))

        self.assertIsNone(result["observed_inputs"]["cpu_utilization_percent"])
        self.assertIn("cpu_utilization_percent", result["unavailable_inputs"])

    def test_nonfinite_values_are_unavailable(self) -> None:
        result = simulate_policy(snapshot(battery=nan, cpu=inf, temperature=-inf))

        self.assertIsNone(result["observed_inputs"]["battery_percent"])
        self.assertIsNone(result["observed_inputs"]["cpu_utilization_percent"])
        self.assertIsNone(result["observed_inputs"]["temperature_c"])
        self.assertEqual(
            result["unavailable_inputs"],
            ["battery_percent", "cpu_utilization_percent", "temperature_c"],
        )

    def test_temperature_outside_plausible_range_is_unavailable(self) -> None:
        result = simulate_policy(snapshot(temperature=126))

        self.assertIsNone(result["observed_inputs"]["temperature_c"])
        self.assertIn("temperature_c", result["unavailable_inputs"])

    def test_repeated_calls_are_identical(self) -> None:
        input_snapshot = snapshot(battery=18, cpu=81, temperature=86)

        self.assertEqual(simulate_policy(input_snapshot), simulate_policy(input_snapshot))

    def test_does_not_invoke_host_controls(self) -> None:
        result = simulate_policy(snapshot(battery=5, cpu=99, temperature=100))

        self.assertTrue(result["simulation_only"])
        self.assertTrue(all(name.startswith("hypothetical_") for name in result["recommendations"]))


if __name__ == "__main__":
    unittest.main()