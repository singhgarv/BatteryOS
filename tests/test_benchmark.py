import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from batteryos.benchmark.analysis import METRIC_NAMES, analyze_run
from batteryos.benchmark.environment import collect_environment
from batteryos.benchmark.store import BenchmarkStore
from batteryos.benchmark.workloads import WORKLOADS, describe_workload
from batteryos.daemon.service import BatteryDaemon


def make_sample(
    timestamp: str,
    *,
    battery_percent: float | None = 80,
    energy_wh: float | None = 20.0,
    power_w: float | None = 10.0,
    cpu_percent: float | None = 20.0,
    temperature_c: float | None = 55.0,
    wifi: bool | None = True,
    ac: bool | None = False,
    provenance: str = "kernel_reported",
) -> dict:
    battery = {
        "battery_level": battery_percent,
        "battery_health": 70,
        "charging": False,
        "ac_connected": ac,
        "power_source": "battery" if ac is False else "ac" if ac is True else "unknown",
        "energy_now_wh": energy_wh,
        "energy_full_wh": 24.0,
        "energy_design_wh": 37.8,
        "voltage_v": 12.0,
        "current_a": power_w / 12 if power_w is not None else None,
        "power_w": power_w,
        "discharge_rate_w": power_w,
        "measurement_provenance": {
            "energy_now_wh": provenance if energy_wh is not None else None,
            "energy_full_wh": "kernel_reported",
            "energy_design_wh": "kernel_reported",
            "power_w": provenance if power_w is not None else None,
        },
        "batteries": [
            {
                "status": "Discharging" if ac is False else "Charging" if ac is True else "unknown",
                "energy_now_wh": energy_wh,
                "power_w": power_w,
                "voltage_v": 12.0,
                "current_a": power_w / 12 if power_w is not None else None,
                "measurement_provenance": {
                    "power_w": provenance if power_w is not None else None,
                },
            }
        ],
    }
    return {
        "schema_version": 1,
        "timestamp": timestamp,
        "battery": battery,
        "cpu": {
            "utilization_percent": cpu_percent,
            "frequency": {"current_khz": 1_600_000},
            "load_average": {"1m": 0.5, "5m": 0.4, "15m": 0.3},
        },
        "thermal": {
            "zones": [{"name": "CPU Package", "temperature_c": temperature_c}],
        },
        "devices": {"wifi_connected": wifi, "backlight_percent": 50},
        "power": {"name": "balanced", "source": "test", "status": "available"},
        "errors": [],
    }


class WorkloadTests(unittest.TestCase):
    def test_supported_workloads_are_descriptive_and_do_not_execute(self) -> None:
        self.assertEqual(set(WORKLOADS), {"idle", "cpu-placeholder", "manual"})
        self.assertEqual(WORKLOADS["cpu-placeholder"].execution, "not_implemented")
        self.assertEqual(WORKLOADS["manual"].execution, "user_controlled")
        self.assertEqual(describe_workload("manual", "reading a web page")["description"], "reading a web page")
        with self.assertRaises(ValueError):
            describe_workload("run-arbitrary-command")


class EnvironmentMetadataTests(unittest.TestCase):
    def test_records_os_cpu_memory_and_observed_start_conditions_without_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            cpuinfo = root / "cpuinfo"
            meminfo = root / "meminfo"
            cpuinfo.write_text("model name : Test CPU\n", encoding="utf-8")
            meminfo.write_text("MemTotal: 1024 kB\n", encoding="utf-8")
            fake_platform = SimpleNamespace(
                system=lambda: "Linux",
                release=lambda: "test-release",
                version=lambda: "test-kernel",
                machine=lambda: "x86_64",
                processor=lambda: "Test CPU",
            )
            sample = make_sample("2026-09-28T12:00:00Z")

            metadata = collect_environment(
                sample,
                cpuinfo_path=cpuinfo,
                meminfo_path=meminfo,
                platform_module=fake_platform,
            )

        self.assertEqual(metadata["os_name"], "Linux")
        self.assertEqual(metadata["cpu_model"], "Test CPU")
        self.assertEqual(metadata["memory_total_bytes"], 1_048_576)
        self.assertEqual(metadata["battery_design_energy_wh_at_start"], 37.8)
        self.assertEqual(metadata["screen_brightness_percent_at_start"], 50)
        self.assertNotIn("hostname", metadata)
        self.assertNotIn("username", metadata)


class BenchmarkStoreTests(unittest.TestCase):
    def test_run_creation_append_and_completion_preserve_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            initial = make_sample("2026-09-28T12:00:00Z")
            run = store.start(
                initial,
                workload_name="idle",
                test_name="browser-idle",
                description="manual browser test",
            )
            middle = make_sample("2026-09-28T12:05:00Z", battery_percent=76, energy_wh=19.0)
            final = make_sample("2026-09-28T12:10:00Z", battery_percent=70, energy_wh=18.0)

            self.assertTrue(store.append_sample(middle))
            completed = store.stop(final)
            loaded = store.get_run(run["run_id"])

            self.assertIsNone(store.active_run())
            self.assertEqual(store.list_runs()[0]["run_id"], run["run_id"])

        self.assertEqual(completed["state"], "completed")
        self.assertEqual(completed["start_timestamp"], initial["timestamp"])
        self.assertEqual(completed["end_timestamp"], final["timestamp"])
        self.assertEqual(completed["workload"]["start_timestamp"], initial["timestamp"])
        self.assertEqual(completed["workload"]["end_timestamp"], final["timestamp"])
        self.assertEqual(completed["initial_battery_state"]["energy_now_wh"], 20.0)
        self.assertEqual(completed["final_battery_state"]["energy_now_wh"], 18.0)
        self.assertEqual(len(loaded["telemetry_samples"]), 3)
        self.assertEqual(completed["environment"]["battery_design_energy_wh_at_start"], 37.8)

    def test_rejects_second_active_run_and_stop_without_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            sample = make_sample("2026-09-28T12:00:00Z")
            store.start(sample)
            with self.assertRaises(RuntimeError):
                store.start(sample)
            store.stop(sample)
            self.assertIsNone(store.stop(sample))

    def test_rejects_invalid_workload_and_run_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            with self.assertRaises(ValueError):
                store.start(make_sample("2026-09-28T12:00:00Z"), workload_name="exec")
            with self.assertRaises(ValueError):
                store.get_run("../../etc/passwd")

    def test_manual_workload_boundaries_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            start = make_sample("2026-09-28T12:00:00Z")
            workload_start = make_sample("2026-09-28T12:02:00Z")
            workload_stop = make_sample("2026-09-28T12:08:00Z")
            run = store.start(start, workload_name="manual")

            self.assertIsNone(run["workload"]["start_timestamp"])
            with self.assertRaises(RuntimeError):
                store.mark_workload_stop(workload_stop)
            store.mark_workload_start(workload_start)
            store.mark_workload_stop(workload_stop)
            completed = store.stop(make_sample("2026-09-28T12:10:00Z"))

        self.assertEqual(completed["workload"]["start_timestamp"], workload_start["timestamp"])
        self.assertEqual(completed["workload"]["end_timestamp"], workload_stop["timestamp"])

    def test_skips_corrupt_run_manifest_when_listing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            store.runs_directory.mkdir(parents=True)
            (store.runs_directory / "corrupt.json").write_text("{bad", encoding="utf-8")
            run = store.start(make_sample("2026-09-28T12:00:00Z"))

            listed = store.list_runs()

        self.assertEqual([item["run_id"] for item in listed], [run["run_id"]])

    def test_daemon_appends_periodic_samples_to_active_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = BenchmarkStore(temporary_directory)
            first = make_sample("2026-09-28T12:00:00Z")
            middle = make_sample("2026-09-28T12:01:00Z")
            store.start(first)
            daemon = BatteryDaemon(
                collector=Mock(collect=Mock(return_value=middle)),
                logger=Mock(),
                benchmark_store=store,
            )

            daemon.run(once=True)
            active = store.active_run()

        self.assertEqual(len(active["telemetry_samples"]), 2)
        self.assertEqual(active["telemetry_samples"][1]["timestamp"], middle["timestamp"])


class BenchmarkAnalysisTests(unittest.TestCase):
    def make_run(self, samples: list, *, start: str, end: str) -> dict:
        return {
            "schema_version": 1,
            "run_id": "test-run",
            "state": "completed",
            "test_name": "test",
            "start_timestamp": start,
            "end_timestamp": end,
            "initial_battery_state": samples[0]["battery"] if samples and isinstance(samples[0], dict) else None,
            "final_battery_state": samples[-1]["battery"] if samples and isinstance(samples[-1], dict) else None,
            "telemetry_samples": samples,
            "description": "test run",
            "workload": {
                "name": "idle",
                "execution": "observe_only",
                "start_timestamp": start,
                "end_timestamp": end,
            },
            "configuration": {"telemetry_schema_version": 1},
            "environment": {"battery_design_energy_wh_at_start": 37.8},
        }

    def test_report_calculates_battery_energy_power_cpu_temperature_and_runtime(self) -> None:
        first = make_sample("2026-09-28T12:00:00Z", battery_percent=80, energy_wh=20, power_w=10, cpu_percent=20, temperature_c=50)
        second = make_sample("2026-09-28T12:10:00Z", battery_percent=70, energy_wh=18, power_w=14, cpu_percent=40, temperature_c=60)
        report = analyze_run(
            self.make_run([first, second], start=first["timestamp"], end=second["timestamp"])
        )

        self.assertEqual(report["battery_percentage_point_change"], -10)
        self.assertEqual(report["energy_remaining_change_wh"], -2)
        self.assertEqual(report["energy_change_class"], "kernel_reported")
        self.assertEqual(report["average_power"]["value_w"], 12)
        self.assertEqual(report["average_power"]["value_class"], "kernel_reported")
        self.assertEqual(report["average_cpu_utilization_percent"], 30)
        self.assertEqual(report["average_temperature_c"], 55)
        self.assertEqual(report["duration_seconds"], 600)
        self.assertEqual(report["workload_duration_seconds"], 600)
        self.assertEqual(report["sample_count"], 2)
        self.assertTrue(report["timestamps_monotonic"])
        self.assertEqual(report["timestamp_order_errors"], 0)
        self.assertEqual(report["missing_data_percentage"], 0)
        self.assertEqual(report["environment"]["battery_design_energy_wh_at_start"], 37.8)

    def test_estimates_average_power_from_energy_delta_when_power_missing(self) -> None:
        first = make_sample("2026-09-28T12:00:00Z", energy_wh=20, power_w=None)
        second = make_sample("2026-09-28T12:30:00Z", energy_wh=18, power_w=None)
        report = analyze_run(self.make_run([first, second], start=first["timestamp"], end=second["timestamp"]))

        self.assertEqual(report["average_power"]["value_w"], 4)
        self.assertEqual(report["average_power"]["value_class"], "calculated_estimate")
        self.assertEqual(report["average_power"]["method"], "energy delta divided by elapsed time")

    def test_does_not_estimate_discharge_power_while_on_ac(self) -> None:
        first = make_sample("2026-09-28T12:00:00Z", energy_wh=20, power_w=None, ac=True)
        second = make_sample("2026-09-28T12:30:00Z", energy_wh=18, power_w=None, ac=True)
        report = analyze_run(self.make_run([first, second], start=first["timestamp"], end=second["timestamp"]))

        self.assertIsNone(report["average_power"])

    def test_does_not_estimate_discharge_power_when_energy_increases(self) -> None:
        first = make_sample("2026-09-28T12:00:00Z", energy_wh=18, power_w=None)
        second = make_sample("2026-09-28T12:30:00Z", energy_wh=20, power_w=None)
        report = analyze_run(self.make_run([first, second], start=first["timestamp"], end=second["timestamp"]))

        self.assertIsNone(report["average_power"])

    def test_incomplete_and_corrupt_samples_contribute_to_missing_data(self) -> None:
        first = make_sample("2026-09-28T12:00:00Z")
        partial = {"timestamp": "2026-09-28T12:01:00Z", "battery": {"battery_level": 79}}
        report = analyze_run(self.make_run([first, partial, "corrupt"], start=first["timestamp"], end=partial["timestamp"]))

        self.assertEqual(report["sample_count"], 2)
        self.assertEqual(report["invalid_sample_count"], 1)
        self.assertGreater(report["missing_data_percentage"], 0)
        self.assertEqual(report["metric_slot_count"], 3 * len(METRIC_NAMES))

    def test_reports_nonmonotonic_and_invalid_timestamps(self) -> None:
        first = make_sample("2026-09-28T12:02:00Z")
        second = make_sample("2026-09-28T12:01:00Z")
        invalid = make_sample("not-a-timestamp")
        report = analyze_run(
            self.make_run([first, second, invalid], start=first["timestamp"], end=second["timestamp"])
        )

        self.assertFalse(report["timestamps_monotonic"])
        self.assertEqual(report["timestamp_order_errors"], 1)
        self.assertEqual(report["invalid_sample_count"], 1)

    def test_empty_run_has_null_statistics_not_fake_zeroes(self) -> None:
        report = analyze_run({"telemetry_samples": []})

        self.assertEqual(report["sample_count"], 0)
        self.assertIsNone(report["battery_percentage_point_change"])
        self.assertIsNone(report["average_power"])
        self.assertIsNone(report["missing_data_percentage"])


class BenchmarkCliTests(unittest.TestCase):
    def test_start_status_stop_list_and_report_commands(self) -> None:
        from batteryos.cli.batteryctl import main

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            benchmark_directory = root / "benchmarks"
            log_file = root / "events.jsonl"
            commands = [
                ["benchmark", "start", "--workload", "manual", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "status", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "workload-start", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "workload-stop", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "stop", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "list", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
                ["benchmark", "report", "--benchmark-directory", str(benchmark_directory), "--log-file", str(log_file)],
            ]
            outputs = []
            for command in commands:
                with patch("sys.argv", ["batteryctl", *command]), patch("builtins.print") as output:
                    main()
                    outputs.append(output.call_args.args[0])

        start_result = json.loads(outputs[0])
        self.assertEqual(start_result["state"], "running")
        self.assertIn(start_result["run_id"], outputs[1])
        self.assertIn('"start_timestamp"', outputs[2])
        self.assertIn('"end_timestamp"', outputs[3])
        stop_report = json.loads(outputs[4])
        self.assertEqual(stop_report["state"], "completed")
        self.assertIn(start_result["run_id"], outputs[5])
        self.assertEqual(json.loads(outputs[6])["run_id"], start_result["run_id"])


if __name__ == "__main__":
    unittest.main()