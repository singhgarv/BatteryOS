import tempfile
import unittest
from pathlib import Path

from scripts.validate_linux_hardware import inspect_linux_interfaces


class LinuxHardwareValidationTests(unittest.TestCase):
    def write(self, path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value, encoding="utf-8")

    def test_inventory_reads_expected_interfaces_without_modifying_them(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            power = root / "power_supply"
            battery = power / "BAT0"
            mains = power / "AC"
            self.write(battery / "type", "Battery")
            self.write(battery / "status", "Discharging")
            self.write(battery / "energy_now", "18000000")
            self.write(battery / "energy_full", "24000000")
            self.write(battery / "energy_full_design", "37802000")
            self.write(battery / "voltage_now", "12000000")
            self.write(battery / "current_now", "500000")
            self.write(battery / "power_now", "6000000")
            self.write(mains / "type", "Mains")
            self.write(mains / "online", "0")

            proc = root / "proc"
            proc_stat = proc / "stat"
            self.write(proc_stat, "cpu 100 0 50 850 0\ncpu0 100 0 50 850 0\n")
            self.write(proc / "cpuinfo", "processor : 0\nmodel name : Fixture CPU\n")
            self.write(proc / "loadavg", "0.10 0.20 0.30 1/100 1000\n")

            cpu_root = root / "sys/devices/system/cpu"
            policy = cpu_root / "cpu0/cpufreq"
            self.write(policy / "scaling_cur_freq", "1600000")
            self.write(policy / "scaling_min_freq", "400000")
            self.write(policy / "scaling_max_freq", "4700000")

            thermal_root = root / "sys/class/thermal"
            self.write(thermal_root / "thermal_zone0/type", "x86_pkg_temp")
            self.write(thermal_root / "thermal_zone0/temp", "61000")
            self.write(thermal_root / "cooling_device0/cur_state", "0")

            hwmon_root = root / "sys/class/hwmon"
            self.write(hwmon_root / "hwmon0/name", "coretemp")
            self.write(hwmon_root / "hwmon0/temp1_label", "Package id 0")
            self.write(hwmon_root / "hwmon0/temp1_input", "61000")

            backlight_root = root / "sys/class/backlight"
            self.write(backlight_root / "intel_backlight/max_brightness", "1000")
            brightness_path = backlight_root / "intel_backlight/brightness"
            self.write(brightness_path, "400")

            network_root = root / "sys/class/net"
            self.write(network_root / "wlan0/wireless/placeholder", "")
            self.write(network_root / "wlan0/operstate", "up")
            self.write(network_root / "wlan0/carrier", "1")

            report = inspect_linux_interfaces(
                power_supply_root=power,
                proc_stat_path=proc_stat,
                cpuinfo_path=proc / "cpuinfo",
                loadavg_path=proc / "loadavg",
                cpu_root=cpu_root,
                thermal_root=thermal_root,
                hwmon_root=hwmon_root,
                backlight_root=backlight_root,
                network_root=network_root,
                system_name="Linux",
                profile_reader=lambda: {"status": "fixture"},
            )

            self.assertTrue(report["supported"])
            self.assertEqual(report["interfaces"]["power_supplies"][0]["name"], "AC")
            self.assertEqual(report["batteryos_snapshot"]["battery"]["ac_connected"], False)
            self.assertEqual(report["batteryos_snapshot"]["battery"]["energy_design_wh"], 37.802)
            self.assertEqual(report["interfaces"]["cpu"]["cpu_models"], ["Fixture CPU"])
            self.assertEqual(report["interfaces"]["cpu"]["frequency_policies"][0]["attributes"]["scaling_cur_freq"], "1600000")
            self.assertEqual(report["interfaces"]["thermal"]["thermal_zones"][0]["temperature_c"], 61.0)
            self.assertEqual(report["interfaces"]["backlights"][0]["attributes"]["brightness"], "400")
            self.assertEqual(report["interfaces"]["wireless_interfaces"][0]["carrier"], "1")
            self.assertEqual(brightness_path.read_text(encoding="utf-8"), "400")
            self.assertEqual((mains / "online").read_text(encoding="utf-8"), "0")
            self.assertNotIn("serial", report)
            self.assertNotIn("hostname", report)

    def test_non_linux_environment_is_reported_as_unsupported(self) -> None:
        report = inspect_linux_interfaces(system_name="Windows")

        self.assertFalse(report["supported"])
        self.assertIn("requires Linux", report["reason"])


if __name__ == "__main__":
    unittest.main()