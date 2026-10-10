import tempfile
import unittest
from pathlib import Path

from sensors.telemetry import CpuUsageSensor, WifiSensor
from settings.backlight import BacklightController
from ui.render import render_taskbar


class CpuUsageSensorTests(unittest.TestCase):
    def test_computes_cpu_usage_from_consecutive_proc_stat_samples(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            stat_path = Path(temporary_directory) / "stat"
            sensor = CpuUsageSensor(stat_path)
            stat_path.write_text("cpu 100 0 50 850 0\n", encoding="utf-8")
            self.assertIsNone(sensor.read_percent())

            stat_path.write_text("cpu 150 0 70 980 0\n", encoding="utf-8")

            self.assertEqual(sensor.read_percent(), 35)

    def test_reads_load_average_frequency_and_per_core_cpu(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            stat_path = root / "stat"
            loadavg_path = root / "loadavg"
            cpu_root = root / "cpu"
            policy = cpu_root / "cpufreq"
            policy.mkdir(parents=True)
            stat_path.write_text(
                "cpu 100 0 50 850 0\ncpu0 50 0 20 430 0\n", encoding="utf-8"
            )
            loadavg_path.write_text("0.50 0.40 0.30 1/100 1234\n", encoding="utf-8")
            (policy / "scaling_cur_freq").write_text("1800000\n", encoding="utf-8")
            (policy / "scaling_min_freq").write_text("400000\n", encoding="utf-8")
            (policy / "scaling_max_freq").write_text("4700000\n", encoding="utf-8")
            (policy / "scaling_available_frequencies").write_text(
                "400000 1800000 4700000\n", encoding="utf-8"
            )
            sensor = CpuUsageSensor(stat_path, loadavg_path, cpu_root)

            self.assertIsNone(sensor.read_percent())
            self.assertIsNone(sensor.read_per_core_percent()["cpu0"])
            stat_path.write_text(
                "cpu 150 0 70 980 0\ncpu0 80 0 30 490 0\n", encoding="utf-8"
            )

            telemetry = sensor.read_telemetry()

        self.assertEqual(telemetry["utilization_percent"], 35)
        self.assertEqual(telemetry["per_core_utilization_percent"]["cpu0"], 40)
        self.assertEqual(telemetry["load_average"]["5m"], 0.4)
        self.assertEqual(telemetry["frequency"]["current_khz"], 1_800_000)
        self.assertEqual(telemetry["frequency"]["available_khz"], [400_000, 1_800_000, 4_700_000])

    def test_reports_unknown_for_invalid_cpu_data(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            stat_path = Path(temporary_directory) / "stat"
            stat_path.write_text("not cpu data\n", encoding="utf-8")

            self.assertIsNone(CpuUsageSensor(stat_path).read_percent())


class WifiSensorTests(unittest.TestCase):
    def make_interface(self, root: Path, name: str, state: str, carrier: str) -> None:
        interface = root / name
        interface.mkdir()
        (interface / "wireless").mkdir()
        (interface / "operstate").write_text(state, encoding="utf-8")
        (interface / "carrier").write_text(carrier, encoding="utf-8")

    def test_reports_connected_and_disconnected_wireless(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            self.make_interface(root, "wlan0", "up", "1")
            self.assertIs(WifiSensor(root).is_connected(), True)

            (root / "wlan0" / "operstate").write_text("down", encoding="utf-8")
            (root / "wlan0" / "carrier").write_text("0", encoding="utf-8")
            self.assertIs(WifiSensor(root).is_connected(), False)

    def test_reports_unknown_when_no_wireless_device_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            self.assertIsNone(WifiSensor(temporary_directory).is_connected())


class BacklightControllerTests(unittest.TestCase):
    def test_reads_and_sets_backlight_percentage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            device = Path(temporary_directory) / "intel_backlight"
            device.mkdir()
            (device / "max_brightness").write_text("1000", encoding="utf-8")
            brightness_path = device / "brightness"
            brightness_path.write_text("500", encoding="utf-8")
            controller = BacklightController(temporary_directory)

            self.assertEqual(controller.read_percent(), 50)
            self.assertEqual(controller.set_percent(35), "Brightness set to 35% (350/1000).")
            self.assertEqual(brightness_path.read_text(encoding="utf-8"), "350\n")

    def test_rejects_zero_brightness_and_missing_devices(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            controller = BacklightController(temporary_directory)

            self.assertIn("between 1 and 100", controller.set_percent(0))
            self.assertIn("No controllable backlight", controller.set_percent(50))


class TelemetryDisplayTests(unittest.TestCase):
    def test_taskbar_does_not_invent_cpu_or_wifi_values(self) -> None:
        rendered = render_taskbar(
            {
                "battery_health": None,
                "battery_level": None,
                "charging": None,
                "power_mode": "Battery Saver",
                "time": "10:00 AM",
                "date": "Mon, Sep 28",
                "cpu_usage": None,
                "wifi_connected": None,
            }
        )

        self.assertIn("CPU N/A", rendered)
        self.assertIn("Wi-Fi Unknown", rendered)


if __name__ == "__main__":
    unittest.main()