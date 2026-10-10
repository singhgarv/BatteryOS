from power.profile_manager import POWER_PROFILE_MANAGER


def show_power_settings() -> str:
    current = POWER_PROFILE_MANAGER.get_current_mode()
    policy = POWER_PROFILE_MANAGER.get_current_policy()
    profiles = ", ".join(mode.name for mode in POWER_PROFILE_MANAGER.list_modes())
    return (
        f"Power profile: {current.name}\n"
        f"CPU limit: {policy['cpu_limit']}%\n"
        f"Idle timeout: {policy['idle_timeout']} seconds\n"
        f"Background policy: {policy['background']}\n"
        f"Available profiles: {profiles}\n"
        "Change with: settings power set <profile>"
    )


def update_power_settings(arguments: str) -> str:
    action, _, profile = arguments.strip().partition(" ")
    if action.casefold() != "set" or not profile.strip():
        return "Usage: settings power set <profile>"
    return POWER_PROFILE_MANAGER.set_mode(profile.strip())