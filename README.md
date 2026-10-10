# BatteryOS Telemetry Prototype

BatteryOS is a Linux userspace power-management research project. Its intended contribution is a measurable, adaptive policy that improves energy efficiency while preserving acceptable performance, responsiveness, and thermal behavior.

**This milestone is telemetry-only. BatteryOS has not demonstrated improved battery life.** No BatteryOS daemon code changes power settings.

## Architecture

```text
Linux kernel interfaces
        |
        +-- battery-d: read telemetry and write structured events
        |      +-- battery, AC, CPU, thermal, and supported device telemetry
        |      +-- current profile inspection (read-only)
        |
        +-- batteryctl: read-only status, telemetry, log, and stats CLI
        |
        +-- JSONL event log in the user's state directory
```

The new implementation is under `src/batteryos/`. It reuses the existing mockable Linux readers in `sensors/` and `thermal/` rather than replacing them. It uses only the Python standard library and existing project modules.

### Telemetry and event schema

Each `telemetry.sample` log event has this stable envelope:

```json
{
  "schema_version": 1,
  "timestamp": "2026-09-28T12:00:00Z",
  "event_type": "telemetry.sample",
  "data": { "snapshot": {} }
}
```

The snapshot carries observed battery values/capacities, explicit AC state, CPU utilization/load/frequency, enumerated thermal zones, supported Wi-Fi/backlight state, current profile when available, and per-source errors. `telemetry.error` events record individual source errors. Capacity values are read from the host at runtime; development-laptop specifications are not used as battery readings.

Default logs are written to `$XDG_STATE_HOME/batteryos/events.jsonl`, or `~/.local/state/batteryos/events.jsonl` when `XDG_STATE_HOME` is unset. On Windows development hosts, the fallback is under `%LOCALAPPDATA%\state\batteryos\events.jsonl`. Pass `--log-file` to either command to choose another location.

## Development Setup

From the repository root, using PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

On Linux, create and activate a virtual environment with `python3 -m venv .venv`, activate it, then run `python -m pip install -e .`. Installation is into the active environment; it does not install a system service or change host power settings.

## Run

Collect one sample and exit:

```text
battery-d --once
```

Run continuous foreground sampling every 10 seconds; stop with Ctrl-C:

```text
battery-d
battery-d --interval 5
battery-d --interval 5 --benchmark-directory /path/to/benchmarks
```

Without installing the console scripts, from the repository root use `PYTHONPATH=src python -m batteryos.cli.battery_d` (module name uses underscore) and `PYTHONPATH=src python -m batteryos.cli.batteryctl`.

Inspect the latest logged sample or query one fresh read-only snapshot:

```text
batteryctl status
batteryctl status --refresh
batteryctl battery
batteryctl cpu
batteryctl thermal
batteryctl logs
batteryctl logs --limit 100
batteryctl stats
batteryctl profile
```

Telemetry subcommands display the newest sample written by `battery-d`; `--refresh` collects a fresh in-memory read without changing the system or writing a log. `batteryctl logs` reads the event log, and `batteryctl stats` computes descriptive summaries from logged samples. `batteryctl profile` only queries `powerprofilesctl get` on Linux. It never selects or changes a profile. If no sample is logged yet, run `battery-d --once` first or use `batteryctl status --refresh`.

Run the full test suite:

```text
python -m unittest discover -v
```

## Hardware and Permissions

- Battery, AC/online power-supply, CPU, thermal-zone, Wi-Fi, and backlight data are read from standard Linux interfaces when present.
- Battery design/full-charge capacity and current energy are observed from sysfs per machine. No current laptop capacity is hardcoded into this telemetry path.
- CPU utilization needs consecutive samples; its first value may be unavailable. Frequency, load, per-core readings, thermal zones, and devices may be absent depending on kernel, firmware, driver, or permissions.
- Missing or unreadable sources are reported as `null`/unavailable with source errors; one failed sensor does not stop other collection.
- Telemetry and current-profile inspection are designed to run without root. Reading particular hardware attributes may be restricted by the host.
- Logs require write access only to the selected user log directory.
- This milestone performs no sysfs writes, profile changes, CPU-frequency changes, USB autosuspend, PCIe changes, kernel parameter changes, bootloader changes, or systemd installation. The collector is read-only; log files are the only writes.

## Measurement and Benchmarking

BatteryOS does not yet claim to improve battery life. This milestone adds a reproducible way to record telemetry during controlled runs; it does not optimize the machine or launch workloads.

Start the foreground sampler in one terminal:

```text
battery-d --interval 5
```

Start, inspect, and finish a run from another terminal:

```text
batteryctl benchmark start --workload idle --test-name idle-on-battery --description "Idle, screen at 40%, Wi-Fi connected"
batteryctl benchmark status
batteryctl benchmark stop
batteryctl benchmark list
batteryctl benchmark report
```

For a user-controlled workload, mark its exact boundaries without asking BatteryOS to launch anything:

```text
batteryctl benchmark start --workload manual --test-name browser-1080p
batteryctl benchmark workload-start
# Start the workload yourself; leave battery-d sampling in the other terminal.
batteryctl benchmark workload-stop
batteryctl benchmark stop
```

Idle runs begin their workload boundary at `benchmark start` and end it at `benchmark stop`. `cpu-placeholder` is metadata only and does not start a stress process. Manual runs require explicit workload markers; run duration and workload duration are reported separately.

To select a specific completed run, use `batteryctl benchmark report RUN_ID`. Run manifests are stored under the user's BatteryOS state directory in `benchmarks/runs/`; `active.json` identifies the in-progress run. Pass `--benchmark-directory PATH` to both `battery-d` and `batteryctl` to use a separate location. They must use the same benchmark directory (default or explicit) for periodic daemon samples to be associated with the run.

Supported workload labels are `idle`, `cpu-placeholder`, and `manual`. The CPU workload is only a placeholder and does not create CPU load. Manual means the user runs the workload separately. BatteryOS never executes arbitrary commands. `benchmark start` and `stop` take telemetry boundary snapshots; keep `battery-d` running during the test to collect periodic samples between them.

Each JSON run manifest contains a unique run ID, schema version, start/end timestamps, test name and description, workload start/end markers, initial/final battery states, raw telemetry samples, configuration, and environment metadata (OS/kernel/architecture, CPU model, RAM, observed battery capacities, brightness, AC/network state, and BatteryOS version). No hostname, username, serial number, or other machine identity is recorded by the environment collector.

Reports include battery percentage-point and energy changes, measured elapsed time, average CPU utilization and temperature, sample count, and missing-data percentage. Average power uses available battery power samples (with their kernel-reported/calculated provenance); when those are missing but energy and duration exist, it labels the energy-delta calculation as an estimate. Missing/corrupt samples are counted, not replaced with zero. `stats` are descriptive summaries, not a controlled cross-OS comparison or a battery-life claim.

For reproducibility, manually record/control workload, brightness, network state, AC/battery state, background applications, and measurement duration. The run captures available state at start, but does not lock those conditions during a run.

## V0.3 Linux Hardware Validation

The development workspace runs on Windows, not the MX Linux USB. No real MX/MSI hardware interfaces have been inspected here, and no Linux hardware validation is claimed. The read-only inventory script and manual MX checklist are at [docs/mx-linux-v0.3-validation.md](docs/mx-linux-v0.3-validation.md). They collect observed interfaces, run a 2–5 minute idle benchmark, and explicitly skip automated CPU stress because no safe CPU workload is implemented.

## Current Status and Roadmap

The repository retains an earlier CLI/taskbar/apps prototype and an Ubuntu Casper live-USB recipe. These are not the BatteryOS core architecture. The Ubuntu image has not been built or boot-tested and is deferred; the existing MX USB and its boot/persistence configuration have not been modified. MX/Ubuntu packaging must wait until telemetry runs correctly on ordinary Linux.

1. **Current: telemetry and measurement prototype.** Read-only collectors, foreground daemon, versioned logs, benchmark runs/reports, read-only `batteryctl`, and mockable tests.
2. **Validate on Linux.** Verify observed interfaces and permissions on the MSI hardware and another Linux machine.
3. **Controlled baseline.** Run repeatable idle and manually controlled workloads; validate energy/power provenance and missing-data reports.
4. **Cross-OS comparison.** Import compatible Windows, standard Linux, and BatteryOS run manifests and compare only controlled, documented runs.
5. **Policy design.** Propose transparent deterministic policies only after telemetry quality and baseline measurements are established.
6. **Reversible control integration.** Later milestone: evaluate standard Linux interfaces one at a time with explicit privileges, rollback, stability tests, and measurements.
7. **MX integration and packaging.** Only after the daemon and measurement model are reliable; preserve MX kernel, standard Bash/userspace, persistence, recovery path, and boot configuration.
8. **Long-term adaptation.** Consider workload-aware policy only when measurements justify it; no unmeasured battery-life claims.

## Legacy Prototype

The older `shell/`, `ui/`, `apps/`, `settings/`, and related command handlers implement a custom prompt, taskbar, notes/browser actions, and prototype power controls. They are retained during migration for compatibility with the existing 72-test baseline, but are out of the telemetry-first core and should not be expanded. The old `power auto apply` and `thermal tune` commands belong to that legacy path, not `battery-d` or `batteryctl`; do not use them as part of the read-only milestone.
