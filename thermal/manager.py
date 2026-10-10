import platform
import shutil
import subprocess
from collections.abc import Callable

from config import load_config
from power.profile_manager import POWER_PROFILE_MANAGER, PowerProfileManager
from thermal.limits import ThermalLimits
from thermal.monitor import ThermalMonitor


class LinuxPowerProfileBackend:
    PROFILE_NAMES = {
        "battery saver": "power-saver",
        "balanced": "balanced",
        "performance": "performance",
    }

    def __init__(
        self,
        system_name: str | None = None,
        command_path: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ):
        self.system_name = system_name or platform.system()
        self.command_path = command_path if command_path is not None else shutil.which("powerprofilesctl")
        self.runner = runner or subprocess.run

    def apply(self, profile_name: str) -> tuple[bool, str]:
        if self.system_name != "Linux":
            return False, "Hardware power tuning is available only on Linux."
        if self.command_path is None:
            return False, "powerprofilesctl is unavailable; no hardware changes were made."

        system_profile = self.PROFILE_NAMES.get(profile_name)
        if system_profile is None:
            return False, f"Unknown power profile: {profile_name}"

        try:
            result = self.runner(
                [self.command_path, "set", system_profile],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            return False, f"Unable to apply power profile: {error}"

        if result.returncode != 0:
            detail = result.stderr.strip() or f"powerprofilesctl exited with status {result.returncode}"
            return False, f"Unable to apply power profile: {detail}"
        return True, f"Applied Linux power profile: {system_profile}."


class ThermalManager:
    def __init__(
        self,
        monitor: ThermalMonitor | None = None,
        limits: ThermalLimits | None = None,
        profile_manager: PowerProfileManager | None = None,
        backend: LinuxPowerProfileBackend | None = None,
    ):
        self.monitor = monitor or ThermalMonitor()
        if limits is None:
            limits = ThermalLimits(**load_config("defaults.json")["thermal_limits"])
        self.limits = limits
        self.profile_manager = profile_manager or POWER_PROFILE_MANAGER
        self.backend = backend or LinuxPowerProfileBackend()

    def get_status(self) -> dict:
        readings = self.monitor.read_temperatures()
        cpu_markers = (
            "cpu", "core", "package", "pkg", "processor", "coretemp",
            "k10temp", "tctl", "tdie",
        )
        cpu_readings = [
            reading
            for reading in readings
            if any(marker in reading.name.casefold() for marker in cpu_markers)
        ]
        hottest = max(cpu_readings, key=lambda reading: reading.celsius, default=None)
        current_profile = self.profile_manager.get_current_mode().name
        if hottest is None:
            state = "unknown"
            recommended_profile = None
        else:
            state = self.limits.classify(hottest.celsius)
            recommended_profile = self.limits.recommended_profile(state, current_profile)
        return {
            "state": state,
            "temperature_c": hottest.celsius if hottest is not None else None,
            "sensor": hottest.name if hottest is not None else None,
            "readings": readings,
            "current_profile": current_profile,
            "recommended_profile": recommended_profile,
        }

    def format_status(self) -> str:
        status = self.get_status()
        temperature = status["temperature_c"]
        if temperature is None:
            return (
                "Thermal state: unknown\n"
                "CPU temperature: unavailable\n"
                "No CPU temperature sensor was found."
            )

        recommendation = status["recommended_profile"]
        if status["state"] == "normal":
            response = "No thermal adjustment recommended."
        elif status["state"] == "warm":
            response = "Prefer balanced mode and reduce display brightness."
        elif status["state"] == "hot":
            response = "Use battery saver and pause nonessential background work."
        else:
            response = "Critical temperature: use battery saver and stop sustained work."

        return (
            f"Thermal state: {status['state']}\n"
            f"CPU temperature: {temperature:.1f} C ({status['sensor']})\n"
            f"Recommended profile: {recommendation}\n"
            f"Response: {response}"
        )

    def status_line(self) -> str:
        status = self.get_status()
        temperature = status["temperature_c"]
        if temperature is None:
            return "unknown"
        return f"{status['state']} ({temperature:.1f} C)"

    def apply_recommended_profile(self) -> str:
        status = self.get_status()
        recommendation = status["recommended_profile"]
        if recommendation is None:
            return "CPU temperature is unavailable; no profile was changed."
        if status["state"] == "normal":
            return "Temperature is normal; no thermal profile change is needed."

        applied, message = self.backend.apply(recommendation)
        if applied:
            self.profile_manager.set_mode(recommendation)
            return message
        return f"Recommended profile: {recommendation}. {message}"


THERMAL_MANAGER = ThermalManager()