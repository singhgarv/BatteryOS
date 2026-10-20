"""Run deterministic synthetic BatteryOS policy scenarios."""

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = REPOSITORY_ROOT / "src"
for import_root in (REPOSITORY_ROOT, SOURCE_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from batteryos.simulation.runner import format_result, run_all, run_scenario, scenarios


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run deterministic BatteryOS policy simulations on synthetic snapshots."
    )
    parser.add_argument(
        "--scenario",
        choices=[scenario.name for scenario in scenarios()],
        help="Run one scenario; omit this option to run all scenarios.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of readable text.",
    )
    arguments = parser.parse_args()
    runs: list[dict[str, Any]]
    if arguments.scenario is None:
        runs = run_all()
    else:
        runs = [run_scenario(arguments.scenario)]

    if arguments.json:
        print(json.dumps(runs, indent=2, sort_keys=True))
    else:
        print("\n\n".join(format_result(run) for run in runs))


if __name__ == "__main__":
    main()
