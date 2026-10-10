from config import load_config


class PowerMode:
    def __init__(self, name: str, brightness: int, cpu_limit: int, idle_timeout: int, background_service_policy: str):
        self.name = name
        self.brightness = brightness
        self.cpu_limit = cpu_limit
        self.idle_timeout = idle_timeout
        self.background_service_policy = background_service_policy

    def describe(self) -> str:
        return (
            f"Mode: {self.name}\n"
            f"Brightness: {self.brightness}%\n"
            f"CPU limit: {self.cpu_limit}%\n"
            f"Idle timeout: {self.idle_timeout}s\n"
            f"Background policy: {self.background_service_policy}"
        )


def normalize_mode_name(name: str) -> str:
    return " ".join(name.replace("_", " ").replace("-", " ").casefold().split())


POWER_MODES = {
    name: PowerMode(name=name, **settings)
    for name, settings in load_config("power_profiles.json").items()
}

BATTERY_SAVER = POWER_MODES["battery saver"]
BALANCED = POWER_MODES["balanced"]
PERFORMANCE = POWER_MODES["performance"]
