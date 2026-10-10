from .modes import POWER_MODES, normalize_mode_name


def apply_policy(mode_name: str) -> dict[str, int | str]:
    mode = POWER_MODES.get(normalize_mode_name(mode_name))
    if mode is None:
        return {"brightness": 0, "cpu_limit": 0, "idle_timeout": 0, "background": "unknown"}
    return {
        "brightness": mode.brightness,
        "cpu_limit": mode.cpu_limit,
        "idle_timeout": mode.idle_timeout,
        "background": mode.background_service_policy,
    }
