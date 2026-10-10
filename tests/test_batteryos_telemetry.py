import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from batteryos.daemon.service import BatteryDaemon
from batteryos.hardware.profile import read_current_profile
from batteryos.logging.events import EventLogger
from batteryos.telemetry.collector import TelemetryCollector


class EventLoggerTests(unittest.TestCase):
    def test_writes_versioned_jsonl_events_with_stable_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "events.jsonl"
            logger = EventLogger(path)
            timestamp = "2026-09-28T12:00:00Z"

            event = logger.write("telemetry.sample", {"battery": {"level": 71}}, timestamp)
            decoded = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

        self.assertEqual(event, decoded)
        self.assertEqual(
            set(decoded), {"schema_version", "timestamp", "event_type", "data"}
        )
        self.assertEqual(decoded["schema_version"], 1)
        self.assertEqual(decoded["timestamp"], timestamp)

    def test_reads_recent_valid_events_and_skips_corrupt_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "events.jsonl"
            logger = EventLogger(path)
            logger.write("one", {})
            with path.open("a", encoding="utf-8") as log_file:
                log_file.write("not json\n")
            logger.write("two", {})

            events = logger.read(limit=2)

        self.assertEqual([event["event_type"] for event in events], ["two"])

    def test_rejects_empty_event_type_and_invalid_limit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            logger = EventLogger(Path(temporary_directory) / "events.jsonl")
            with self.assertRaises(ValueError):
                logger.write("", {})
            with self.assertRaises(ValueError):
                logger.read(limit=0)


class TelemetryCollectorTests(unittest.TestCase):
    def test_collects_sources_and_keeps_observed_capacity_values(self) -> None:
        battery = Mock()
        battery.get_status.return_value = {
            "battery_level": 63,
            "battery_health": 72,
            "charging": False,
            "ac_connected": True,
            "power_source": "ac",
            "energy_now_wh": 15.2,
            "energy_full_wh": 24.191,
            "energy_design_wh": 37.802,
            "batteries": [],
            "external_power_supplies": [],
        }
        cpu = Mock()
        cpu.read_telemetry.return_value = {
            "utilization_percent": 12,
            "per_core_utilization_percent": {"cpu0": 10},
            "load_average": {"1m": 0.1, "5m": 0.2, "15m": 0.3},
            "frequency": {"current_khz": 1_200_000},
        }
        thermal = Mock()
        thermal.read_telemetry.return_value = {"zones": [], "hottest_temperature_c": None}
        wifi = Mock()
        wifi.is_connected.return_value = True
        backlight = Mock()
        backlight.read_percent.return_value = 50
        timestamp = datetime(2026, 9, 28, tzinfo=timezone.utc)
        collector = TelemetryCollector(
            battery=battery,
            cpu=cpu,
            thermal=thermal,
            wifi=wifi,
            backlight=backlight,
            profile_reader=lambda: {"name": "balanced", "status": "available"},
            clock=lambda: timestamp,
        )

        sample = collector.collect()

        self.assertEqual(sample["timestamp"], "2026-09-28T00:00:00Z")
        self.assertEqual(sample["battery"]["energy_full_wh"], 24.191)
        self.assertEqual(sample["battery"]["energy_design_wh"], 37.802)
        self.assertIs(sample["battery"]["ac_connected"], True)
        self.assertEqual(sample["cpu"]["frequency"]["current_khz"], 1_200_000)
        self.assertEqual(sample["power"]["name"], "balanced")
        self.assertEqual(sample["errors"], [])

    def test_one_sensor_failure_does_not_fail_other_telemetry(self) -> None:
        battery = Mock()
        battery.get_status.side_effect = PermissionError("battery denied")
        cpu = Mock()
        cpu.read_telemetry.return_value = {"utilization_percent": 7}
        collector = TelemetryCollector(
            battery=battery,
            cpu=cpu,
            thermal=Mock(read_telemetry=Mock(return_value={"zones": []})),
            wifi=Mock(is_connected=Mock(return_value=None)),
            backlight=Mock(read_percent=Mock(return_value=None)),
            profile_reader=lambda: {"status": "unavailable"},
        )

        sample = collector.collect()

        self.assertIsNone(sample["battery"])
        self.assertEqual(sample["cpu"]["utilization_percent"], 7)
        self.assertEqual(sample["errors"][0]["source"], "battery")


class BatteryDaemonTests(unittest.TestCase):
    def test_once_mode_logs_sample_and_source_errors(self) -> None:
        collector = Mock()
        collector.collect.return_value = {
            "schema_version": 1,
            "timestamp": "2026-09-28T12:00:00Z",
            "errors": [{"source": "cpu", "error": "unavailable"}],
        }
        logger = Mock()
        daemon = BatteryDaemon(collector=collector, logger=logger)

        count = daemon.run(once=True)

        self.assertEqual(count, 1)
        self.assertFalse(daemon.running)
        self.assertEqual(logger.write.call_count, 2)
        self.assertEqual(logger.write.call_args_list[0].args[0], "telemetry.sample")
        self.assertEqual(logger.write.call_args_list[1].args[0], "telemetry.error")

    def test_rejects_nonpositive_interval(self) -> None:
        with self.assertRaises(ValueError):
            BatteryDaemon(interval_seconds=0)


class BatteryctlTests(unittest.TestCase):
    def test_profile_command_only_queries_read_only_profile_reader(self) -> None:
        with patch("batteryos.cli.batteryctl.read_current_profile", return_value={"name": "balanced"}) as reader:
            from batteryos.cli.batteryctl import main

            with patch("sys.argv", ["batteryctl", "profile"]), patch("builtins.print") as output:
                main()

        reader.assert_called_once_with()
        self.assertIn("balanced", output.call_args.args[0])

    def test_status_without_events_explains_how_to_collect(self) -> None:
        from batteryos.cli.batteryctl import main

        with tempfile.TemporaryDirectory() as temporary_directory:
            log_path = Path(temporary_directory) / "missing.jsonl"
            with patch("sys.argv", ["batteryctl", "status", "--log-file", str(log_path)]), patch(
                "builtins.print"
            ) as output:
                main()

        self.assertIn("Run battery-d --once", output.call_args.args[0])


class ReadOnlyProfileTests(unittest.TestCase):
    def test_linux_profile_probe_only_runs_get(self) -> None:
        completed = Mock(returncode=0, stdout="balanced\n", stderr="")
        with patch("batteryos.hardware.profile.platform.system", return_value="Linux"), patch(
            "batteryos.hardware.profile.shutil.which", return_value="/usr/bin/powerprofilesctl"
        ), patch("batteryos.hardware.profile.subprocess.run", return_value=completed) as runner:
            profile = read_current_profile()

        self.assertEqual(profile["name"], "balanced")
        self.assertEqual(runner.call_args.args[0], ["/usr/bin/powerprofilesctl", "get"])


if __name__ == "__main__":
    unittest.main()