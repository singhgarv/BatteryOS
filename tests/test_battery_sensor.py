import tempfile
import unittest
from pathlib import Path

from sensors.battery import BatterySensor


class BatterySensorTests(unittest.TestCase):
    def create_battery(self, root: Path, values: dict[str, str]) -> None:
        battery = root / "BAT0"
        battery.mkdir()
        for name, value in values.items():
            (battery / name).write_text(value, encoding="utf-8")

    def test_reads_energy_health_and_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_battery(
                root,
                {
                    "type": "Battery",
                    "status": "Discharging",
                    "energy_now": "5000000",
                    "energy_full": "10000000",
                    "energy_full_design": "12500000",
                    "power_now": "2000000",
                },
            )

            status = BatterySensor(power_supply_path=root).get_status()

        self.assertEqual(status["battery_level"], 50)
        self.assertEqual(status["battery_health"], 80)
        self.assertIs(status["charging"], False)
        self.assertEqual(status["estimated_runtime_hours"], 2.5)
        self.assertEqual(status["energy_now_wh"], 5.0)
        self.assertEqual(status["energy_full_wh"], 10.0)
        self.assertEqual(status["energy_design_wh"], 12.5)
        self.assertEqual(status["discharge_rate_w"], 2.0)
        self.assertEqual(status["batteries"][0]["measurement_provenance"]["power_w"], "kernel_reported")
        self.assertEqual(status["measurement_provenance"]["energy_now_wh"], "kernel_reported")
        self.assertIsNone(status["ac_connected"])

    def test_detects_ac_independently_of_battery_charging_status(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_battery(
                root,
                {
                    "type": "Battery",
                    "status": "Full",
                    "energy_now": "24000000",
                    "energy_full": "24000000",
                    "energy_full_design": "37802000",
                },
            )
            mains = root / "AC"
            mains.mkdir()
            (mains / "type").write_text("Mains", encoding="utf-8")
            (mains / "online").write_text("1", encoding="utf-8")

            status = BatterySensor(power_supply_path=root).get_status()

        self.assertIs(status["charging"], False)
        self.assertIs(status["ac_connected"], True)
        self.assertEqual(status["power_source"], "ac")
        self.assertEqual(status["energy_design_wh"], 37.802)
        self.assertEqual(status["measurement_provenance"]["ac_connected"], "kernel_reported")

    def test_uses_charge_and_voltage_when_energy_fields_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_battery(
                root,
                {
                    "type": "Battery",
                    "status": "Discharging",
                    "charge_now": "2000000",
                    "charge_full": "4000000",
                    "charge_full_design": "5000000",
                    "voltage_now": "12000000",
                    "current_now": "1000000",
                },
            )

            status = BatterySensor(power_supply_path=root).get_status()

        self.assertEqual(status["battery_level"], 50)
        self.assertEqual(status["battery_health"], 80)
        self.assertEqual(status["estimated_runtime_hours"], 2.0)
        self.assertEqual(status["batteries"][0]["measurement_provenance"]["energy_now_wh"], "calculated_estimate")
        self.assertEqual(status["batteries"][0]["measurement_provenance"]["power_w"], "calculated_estimate")

    def test_does_not_estimate_runtime_while_charging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.create_battery(
                root,
                {
                    "type": "Battery",
                    "status": "Charging",
                    "energy_now": "5000000",
                    "energy_full": "10000000",
                    "power_now": "2000000",
                },
            )

            status = BatterySensor(power_supply_path=root).get_status()

        self.assertIs(status["charging"], True)
        self.assertIsNone(status["estimated_runtime_hours"])

    def test_reports_unknown_when_no_battery_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            status = BatterySensor(power_supply_path=temporary_directory).get_status()

        self.assertIsNone(status["battery_level"])
        self.assertIsNone(status["battery_health"])
        self.assertIsNone(status["charging"])
        self.assertIsNone(status["estimated_runtime_hours"])


if __name__ == "__main__":
    unittest.main()