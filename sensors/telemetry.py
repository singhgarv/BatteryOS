from pathlib import Path


class CpuUsageSensor:
    def __init__(
        self,
        stat_path: str | Path = "/proc/stat",
        loadavg_path: str | Path = "/proc/loadavg",
        cpu_root: str | Path = "/sys/devices/system/cpu",
    ):
        self.stat_path = Path(stat_path)
        self.loadavg_path = Path(loadavg_path)
        self.cpu_root = Path(cpu_root)
        self._previous_sample: tuple[int, int] | None = None
        self._previous_cores: dict[str, tuple[int, int]] = {}

    @staticmethod
    def _parse_cpu_counters(fields: list[str]) -> tuple[int, int] | None:
        try:
            counters = [int(value) for value in fields]
        except ValueError:
            return None
        if len(counters) < 4:
            return None
        total = sum(counters)
        idle = counters[3] + (counters[4] if len(counters) > 4 else 0)
        return total, idle

    def _read_counters(self) -> tuple[tuple[int, int] | None, dict[str, tuple[int, int]]]:
        try:
            lines = self.stat_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return None, {}

        aggregate = None
        cores = {}
        for line in lines:
            fields = line.split()
            if not fields or fields[0] != "cpu" and not fields[0].startswith("cpu"):
                continue
            counters = self._parse_cpu_counters(fields[1:])
            if counters is None:
                continue
            if fields[0] == "cpu":
                aggregate = counters
            elif fields[0][3:].isdigit():
                cores[fields[0]] = counters
        return aggregate, cores

    @staticmethod
    def _percent_between(
        previous: tuple[int, int] | None,
        current: tuple[int, int] | None,
    ) -> int | None:
        if previous is None or current is None:
            return None
        total_delta = current[0] - previous[0]
        idle_delta = current[1] - previous[1]
        busy_delta = total_delta - idle_delta
        if total_delta <= 0 or idle_delta < 0 or busy_delta < 0:
            return None
        return max(0, min(100, round(busy_delta * 100 / total_delta)))

    def read_percent(self) -> int | None:
        current_sample, _ = self._read_counters()
        if current_sample is None:
            self._previous_sample = None
            return None

        previous_sample = self._previous_sample
        self._previous_sample = current_sample
        return self._percent_between(previous_sample, current_sample)

    def read_per_core_percent(self) -> dict[str, int | None]:
        _, current_cores = self._read_counters()
        previous_cores = self._previous_cores
        self._previous_cores = current_cores
        return {
            name: self._percent_between(previous_cores.get(name), counters)
            for name, counters in current_cores.items()
        }

    def read_load_average(self) -> dict[str, float] | None:
        try:
            fields = self.loadavg_path.read_text(encoding="utf-8").split()
            if len(fields) < 3:
                return None
            return {"1m": float(fields[0]), "5m": float(fields[1]), "15m": float(fields[2])}
        except (OSError, ValueError):
            return None

    @staticmethod
    def _read_frequency_khz(path: Path) -> int | None:
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def read_frequency(self) -> dict[str, int | None] | None:
        policy_root = self.cpu_root / "cpufreq"
        if not policy_root.exists():
            try:
                policies = sorted(self.cpu_root.glob("cpu[0-9]*/cpufreq"))
            except OSError:
                policies = []
            policy_root = policies[0] if policies else policy_root
        if not policy_root.exists():
            return None

        current = self._read_frequency_khz(policy_root / "scaling_cur_freq")
        if current is None:
            current = self._read_frequency_khz(policy_root / "cpuinfo_cur_freq")
        minimum = self._read_frequency_khz(policy_root / "scaling_min_freq")
        maximum = self._read_frequency_khz(policy_root / "scaling_max_freq")
        available_path = policy_root / "scaling_available_frequencies"
        try:
            available = [int(value) for value in available_path.read_text(encoding="utf-8").split()]
        except (OSError, ValueError):
            available = None
        if current is None and minimum is None and maximum is None and available is None:
            return None
        return {
            "current_khz": current,
            "minimum_khz": minimum,
            "maximum_khz": maximum,
            "available_khz": available,
        }

    def read_telemetry(self) -> dict:
        return {
            "utilization_percent": self.read_percent(),
            "per_core_utilization_percent": self.read_per_core_percent(),
            "load_average": self.read_load_average(),
            "frequency": self.read_frequency(),
        }


class WifiSensor:
    def __init__(self, network_root: str | Path = "/sys/class/net"):
        self.network_root = Path(network_root)

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip().casefold()
        except OSError:
            return None

    def is_connected(self) -> bool | None:
        try:
            interfaces = sorted(self.network_root.iterdir())
        except OSError:
            return None

        wireless_interfaces = [
            interface for interface in interfaces if (interface / "wireless").exists()
        ]
        if not wireless_interfaces:
            return None

        has_disconnected_interface = False
        for interface in wireless_interfaces:
            carrier = self._read_text(interface / "carrier")
            state = self._read_text(interface / "operstate")
            if carrier == "1" and state == "up":
                return True
            if carrier == "0" or state in {"down", "lowerlayerdown"}:
                has_disconnected_interface = True

        if has_disconnected_interface:
            return False
        return None