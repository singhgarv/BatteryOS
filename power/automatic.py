from power.laptop_profile import LaptopProfile, TARGET_LAPTOP
from power.profile_manager import POWER_PROFILE_MANAGER, PowerProfileManager
from sensors.battery import BatterySensor
from thermal.manager import LinuxPowerProfileBackend, THERMAL_MANAGER, ThermalManager


class BatteryAwarePowerPolicy:
    def __init__(
        self,
        battery_sensor: BatterySensor | None = None,
        thermal_manager: ThermalManager | None = None,
        profile_manager: PowerProfileManager | None = None,
        backend: LinuxPowerProfileBackend | None = None,
        laptop_profile: LaptopProfile = TARGET_LAPTOP,
    ):
        self.battery_sensor = battery_sensor or BatterySensor()
        self.thermal_manager = thermal_manager or THERMAL_MANAGER
        self.profile_manager = profile_manager or POWER_PROFILE_MANAGER
        self.backend = backend or self.thermal_manager.backend
        self.laptop_profile = laptop_profile

    def recommend(self) -> dict[str, int | float | str | bool | None]:
        battery = self.battery_sensor.get_status()
        thermal = self.thermal_manager.get_status()
        current_profile = self.profile_manager.get_current_mode().name
        health = battery["battery_health"]
        if health is None:
            health = self.laptop_profile.battery_health_percent

        charging = battery["charging"]
        level = battery["battery_level"]
        thermal_state = thermal["state"]

        if thermal_state in {"hot", "critical"}:
            profile = "battery saver"
            reason = f"CPU thermal state is {thermal_state}; reduce sustained load."
        elif charging is False:
            profile = "battery saver"
            if level is not None and level <= self.laptop_profile.battery_reserve_percent:
                reason = f"Battery is at or below the {self.laptop_profile.battery_reserve_percent}% reserve."
            elif health <= 70:
                reason = f"Battery health is {health}%; conserve the reduced usable capacity."
            else:
                reason = "On battery; prefer low heat, quiet operation, and minimal background work."
        elif charging is True and thermal_state == "normal" and current_profile == "performance":
            profile = "performance"
            reason = "Performance is explicitly selected, the laptop is charging, and CPU temperature is normal."
        elif charging is True:
            profile = "balanced"
            reason = "On external power; use balanced mode unless performance is explicitly requested and thermals are normal."
        else:
            profile = "battery saver"
            reason = "Power source or thermal state is unknown; use the conservative default."

        return {
            "recommended_profile": profile,
            "reason": reason,
            "battery_level": level,
            "battery_health": health,
            "charging": charging,
            "thermal_state": thermal_state,
            "effective_capacity_wh": round(
                self.laptop_profile.battery_design_wh * health / 100, 1
            ),
            "current_profile": current_profile,
        }

    def format_recommendation(self) -> str:
        status = self.recommend()
        battery_level = status["battery_level"]
        level_text = f"{battery_level}%" if battery_level is not None else "unknown"
        charging = status["charging"]
        power_source = "charging" if charging is True else "on battery" if charging is False else "unknown"
        return (
            f"Laptop: {self.laptop_profile.cpu_model}, {self.laptop_profile.memory_gib} GB, {self.laptop_profile.graphics}\n"
            f"Battery: {level_text}, {power_source}\n"
            f"Health: {status['battery_health']}% (about {status['effective_capacity_wh']:g} Wh usable)\n"
            f"Thermal state: {status['thermal_state']}\n"
            f"Current profile: {status['current_profile']}\n"
            f"Recommended profile: {status['recommended_profile']}\n"
            f"Reason: {status['reason']}\n"
            "Apply with: power auto apply"
        )

    def apply_recommendation(self) -> str:
        status = self.recommend()
        profile = str(status["recommended_profile"])
        applied, message = self.backend.apply(profile)
        if not applied:
            return f"Recommended profile: {profile}. {message}"
        self.profile_manager.set_mode(profile)
        return f"{message} Reason: {status['reason']}"


LAPTOP_POWER_POLICY = BatteryAwarePowerPolicy()