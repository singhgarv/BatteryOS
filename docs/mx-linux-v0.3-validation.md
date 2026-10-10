# BatteryOS V0.3: MX Linux Hardware Validation

This checklist is for read-only validation on the MSI Modern 15 B12MO booted into MX Linux Live USB. BatteryOS has not been run against that Linux hardware from the Windows development environment; do not fill in interface results until the commands below have actually run on MX.

## Safety Scope

This milestone reads Linux telemetry only. It must not change CPU governors/frequencies, power profiles, USB power, PCIe, thermal settings, kernel parameters, bootloader/EFI, or Windows. It does not install a service. The inventory script only reads interfaces and writes a JSON report if `--output` is supplied; choose a path in the live user's home, not a system path. No command below uses `sudo`.

The existing `cpu-placeholder` workload does not create CPU load. Do not run a stress tool for this validation. The light-CPU workload section is intentionally marked not run unless a separate controlled manual workload is approved.

## 1. Locate the Repository and Check Python

Find the directory containing `src/batteryos` and `scripts/validate_linux_hardware.py`, then enter it. For example:

```sh
cd /path/to/GBat
python3 --version
uname -a
```

BatteryOS uses Python 3.10+ syntax. Do not install BatteryOS or configure MX boot/session files for this milestone. If the repository is on another USB or partition, access it read-only if practical; store validation output in the live user's home.

## 2. Record Read-Only Interface Inventory

```sh
mkdir -p "$HOME/batteryos-v03"
export PYTHONPATH="$PWD/src"
python3 scripts/validate_linux_hardware.py --output "$HOME/batteryos-v03/hardware-inventory.json"
```

The script records the OS/kernel/architecture, raw discovered values and paths under `/sys/class/power_supply`, `/proc/stat`, `/proc/cpuinfo`, `/proc/loadavg`, `/sys/devices/system/cpu`, `/sys/class/thermal`, `/sys/class/hwmon`, `/sys/class/backlight`, and wireless interfaces under `/sys/class/net`, plus a BatteryOS snapshot. It does not read SSIDs, IP addresses, MAC addresses, serial numbers, usernames, or hostnames.

Check the inventory before benchmarking:

```sh
python3 -m json.tool "$HOME/batteryos-v03/hardware-inventory.json" >/dev/null && echo "Inventory JSON valid"
```

For each interface, report the exact path/name discovered and raw value. `null`/empty means unavailable or unreadable; do not substitute a guessed value.

## 3. Start Read-Only Telemetry

In terminal 1:

```sh
export PYTHONPATH="/path/to/GBat/src"
export BATTERYOS_LOG="$HOME/batteryos-v03/events.jsonl"
export BATTERYOS_BENCH="$HOME/batteryos-v03/benchmarks"
mkdir -p "$HOME/batteryos-v03"
python3 -m batteryos.cli.battery_d --interval 5 --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
```

Leave it running in the foreground. Stop it with Ctrl-C after the benchmark. No system service is installed.

## 4. Idle Benchmark (2–5 Minutes)

In terminal 2, use the same repository and environment variables, then run:

```sh
cd /path/to/GBat
export PYTHONPATH="$PWD/src"
export BATTERYOS_LOG="$HOME/batteryos-v03/events.jsonl"
export BATTERYOS_BENCH="$HOME/batteryos-v03/benchmarks"
python3 -m batteryos.cli.batteryctl benchmark start --workload idle --test-name mx-v03-idle --description "MX Live USB idle; record screen brightness and network state manually" --interval-seconds 5 --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
sleep 180
python3 -m batteryos.cli.batteryctl benchmark status --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
python3 -m batteryos.cli.batteryctl benchmark stop --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
python3 -m batteryos.cli.batteryctl benchmark report --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
```

For a 5-minute run, change `sleep 180` to `sleep 300`. Keep the laptop's normal state unchanged during the run; note whether AC is connected, approximate screen brightness, and whether Wi-Fi is connected.

## 5. Light CPU Activity

There is no built-in CPU workload yet, and `cpu-placeholder` intentionally does nothing. Do not run `stress`, `stress-ng`, or other automatically generated load as part of this milestone. If separately approved, perform an ordinary manual light task and bracket only that task:

```sh
python3 -m batteryos.cli.batteryctl benchmark start --workload manual --test-name mx-v03-manual-light --description "Describe the ordinary manual activity" --interval-seconds 5 --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
python3 -m batteryos.cli.batteryctl benchmark workload-start --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
# Perform only the agreed, ordinary manual activity here.
python3 -m batteryos.cli.batteryctl benchmark workload-stop --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
python3 -m batteryos.cli.batteryctl benchmark stop --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
python3 -m batteryos.cli.batteryctl benchmark report --log-file "$BATTERYOS_LOG" --benchmark-directory "$BATTERYOS_BENCH"
```

If no workload has been approved, mark this test **not run**. Do not represent the `cpu-placeholder` label as actual load.

## 6. Verify Commands and JSONL

With terminal 1 still sampling, run:

```sh
python3 -m batteryos.cli.batteryctl status --refresh --log-file "$BATTERYOS_LOG"
python3 -m batteryos.cli.batteryctl battery --refresh --log-file "$BATTERYOS_LOG"
python3 -m batteryos.cli.batteryctl cpu --refresh --log-file "$BATTERYOS_LOG"
python3 -m batteryos.cli.batteryctl thermal --refresh --log-file "$BATTERYOS_LOG"
python3 -m batteryos.cli.batteryctl profile --log-file "$BATTERYOS_LOG"
python3 -m batteryos.cli.batteryctl logs --limit 5 --log-file "$BATTERYOS_LOG"
```

Verify each JSONL line independently and timestamps are increasing:

```sh
python3 - "$BATTERYOS_LOG" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1])
events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
timestamps = [datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00")) for event in events]
print(f"valid_jsonl_events={len(events)}")
print(f"timestamps_monotonic={all(a <= b for a, b in zip(timestamps, timestamps[1:]))}")
print(f"event_types={sorted({event.get('event_type') for event in events})}")
PY
```

Review each benchmark report for sample count, duration, timestamp ordering, missing-data percentage, battery/AC changes, and power provenance. Charging/AC runs or increasing battery energy must not be reported as battery discharge power. Check plausible values against the raw sysfs inventory, not laptop specification estimates.

## 7. Evidence to Return

Send these files from `$HOME/batteryos-v03`:

- `hardware-inventory.json`
- `events.jsonl`
- the completed JSON manifest from `benchmarks/runs/<run-id>.json`
- the printed `batteryctl benchmark report` output
- the MX command output for `uname -a`, `python3 --version`, and the read-only battery/CPU/thermal/device commands
- manually recorded AC state, screen brightness, workload description, and duration

Do not send personal files or unrelated USB contents. The report intentionally avoids hostname, username, serial number, MAC address, IP address, and SSID collection. BatteryOS makes no power-life claim from this validation.
