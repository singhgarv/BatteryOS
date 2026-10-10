from config import load_config
from .modes import POWER_MODES, PowerMode, normalize_mode_name
from .policies import apply_policy


class PowerProfileManager:
    def __init__(self, current_mode: str | None = None):
        if current_mode is None:
            defaults = load_config("defaults.json")
            current_mode = defaults["power"]["default_profile"]
        mode_key = normalize_mode_name(current_mode)
        if mode_key not in POWER_MODES:
            raise ValueError(f"Unknown power mode: {current_mode}")
        self.current_mode = mode_key

    def set_mode(self, mode_name: str) -> str:
        mode_key = normalize_mode_name(mode_name)
        if mode_key not in POWER_MODES:
            return f"Unknown mode: {mode_name}"
        self.current_mode = mode_key
        return f"Power mode switched to {self.current_mode}"

    def get_current_mode(self) -> PowerMode:
        return POWER_MODES[self.current_mode]

    def get_mode(self, mode_name: str) -> PowerMode | None:
        return POWER_MODES.get(normalize_mode_name(mode_name))

    def list_modes(self) -> list[PowerMode]:
        return list(POWER_MODES.values())

    def get_current_policy(self) -> dict[str, int | str]:
        return apply_policy(self.current_mode)

    def describe_current(self) -> str:
        return self.get_current_mode().describe()


POWER_PROFILE_MANAGER = PowerProfileManager()
