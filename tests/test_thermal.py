import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from power.profile_manager import PowerProfileManager
from thermal.limits import ThermalLimits
from thermal.manager import LinuxPowerProfileBackend, ThermalManager
from thermal.monitor import ThermalMonitor, TemperatureReading


class ThermalMonitorTests(unittest.TestCase):
    def test_reads_cpu_zone_temperature_in_millidegrees(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            zone = root / "thermal_zone0"
            zone.mkdir()
            (zone / "type").write_text("x86_pkg_temp", encoding="utf-8")
            (zone / "temp").write_text("73400", encoding="utf-8")

            readings = ThermalMonitor(thermal_root=root, hwmon_root=root / "missing").read_temperatures()

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].name, "x86_pkg_temp")
        self.assertEqual(readings[0].celsius, 73.4)

    def test_includes_non_cpu_thermal_zones(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            zone = root / "thermal_zone0"
            zone.mkdir()
            (zone / "type").write_text("acpitz", encoding="utf-8")
            (zone / "temp").write_text("55000", encoding="utf-8")

            readings = ThermalMonitor(thermal_root=root, hwmon_root=root / "missing").read_temperatures()

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].name, "acpitz")
        self.assertEqual(readings[0].celsius, 55.0)

    def test_reads_coretemp_hwmon_sensor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            device = root / "hwmon0"
            device.mkdir()
            (device / "name").write_text("coretemp", encoding="utf-8")
            (device / "temp1_label").write_text("Package id 0", encoding="utf-8")
            (device / "temp1_input").write_text("92000", encoding="utf-8")

            readings = ThermalMonitor(
                thermal_root=root / "missing", hwmon_root=root
            ).read_temperatures()

        self.assertEqual(len(readings), 1)
        self.assertEqual(readings[0].celsius, 92.0)

    def test_enumerates_multiple_generic_thermal_zones(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            for index, zone_type, temperature in (
                (0, "cpu-thermal", "68000"),
                (1, "soc-thermal", "72000"),
            ):
                zone = root / f"thermal_zone{index}"
                zone.mkdir()
                (zone / "type").write_text(zone_type, encoding="utf-8")
                (zone / "temp").write_text(temperature, encoding="utf-8")

            readings = ThermalMonitor(
                thermal_root=root, hwmon_root=root / "missing"
            ).read_temperatures()

        self.assertEqual([reading.name for reading in readings], ["cpu-thermal", "soc-thermal"])


class ThermalLimitTests(unittest.TestCase):
    def test_classifies_thresholds_and_recommends_cooler_profiles(self) -> None:
        limits = ThermalLimits()

        self.assertEqual(limits.classify(69.9), "normal")
        self.assertEqual(limits.classify(70), "warm")
        self.assertEqual(limits.classify(85), "hot")
        self.assertEqual(limits.classify(95), "critical")
        self.assertEqual(limits.recommended_profile("warm", "performance"), "balanced")
        self.assertEqual(limits.recommended_profile("hot", "balanced"), "battery saver")

    def test_rejects_invalid_limit_order(self) -> None:
        with self.assertRaises(ValueError):
            ThermalLimits(warm_c=90, hot_c=80, critical_c=95)


class LinuxPowerProfileBackendTests(unittest.TestCase):
    def test_applies_supported_linux_profile(self) -> None:
        runner = Mock(return_value=subprocess.CompletedProcess(args=[], returncode=0, stderr=""))
        backend = LinuxPowerProfileBackend(
            system_name="Linux", command_path="powerprofilesctl", runner=runner
        )

        applied, message = backend.apply("battery saver")

        self.assertTrue(applied)
        self.assertIn("power-saver", message)
        runner.assert_called_once_with(
            ["powerprofilesctl", "set", "power-saver"],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_missing_linux_backend_does_not_run_command(self) -> None:
        runner = Mock()
        backend = LinuxPowerProfileBackend(system_name="Linux", command_path=None, runner=runner)

        applied, message = backend.apply("battery saver")

        self.assertFalse(applied)
        self.assertIn("unavailable", message)
        runner.assert_not_called()


class ThermalManagerTests(unittest.TestCase):
    def test_status_recommends_battery_saver_for_hot_cpu(self) -> None:
        monitor = Mock()
        monitor.read_temperatures.return_value = [
            TemperatureReading(name="CPU Package", celsius=88.0, source="test")
        ]
        profiles = PowerProfileManager("performance")
        manager = ThermalManager(
            monitor=monitor,
            profile_manager=profiles,
            backend=Mock(),
        )

        status = manager.get_status()

        self.assertEqual(status["state"], "hot")
        self.assertEqual(status["recommended_profile"], "battery saver")
        self.assertIn("88.0 C", manager.format_status())

    def test_apply_changes_profile_only_after_backend_succeeds(self) -> None:
        monitor = Mock()
        monitor.read_temperatures.return_value = [
            TemperatureReading(name="CPU Package", celsius=96.0, source="test")
        ]
        profiles = PowerProfileManager("performance")
        backend = Mock()
        backend.apply.return_value = (True, "Applied Linux power profile: power-saver.")
        manager = ThermalManager(monitor=monitor, profile_manager=profiles, backend=backend)

        self.assertIn("Applied Linux", manager.apply_recommended_profile())
        self.assertEqual(profiles.get_current_mode().name, "battery saver")

        backend.apply.return_value = (False, "no backend")
        profiles.set_mode("performance")
        manager.apply_recommended_profile()
        self.assertEqual(profiles.get_current_mode().name, "performance")

    def test_missing_temperature_never_changes_profile(self) -> None:
        monitor = Mock()
        monitor.read_temperatures.return_value = []
        profiles = PowerProfileManager("performance")
        manager = ThermalManager(monitor=monitor, profile_manager=profiles, backend=Mock())

        self.assertIn("unavailable", manager.apply_recommended_profile())
        self.assertEqual(profiles.get_current_mode().name, "performance")


if __name__ == "__main__":
    unittest.main()