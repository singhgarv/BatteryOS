from power.profile_manager import POWER_PROFILE_MANAGER
from settings.backlight import BacklightController

BACKLIGHT_CONTROLLER = BacklightController()


def show_display_settings() -> str:
    mode = POWER_PROFILE_MANAGER.get_current_mode()
    brightness = BACKLIGHT_CONTROLLER.read_percent()
    brightness_text = f"{brightness}%" if brightness is not None else "unavailable"
    return (
        f"Display brightness target: {mode.brightness}%\n"
        f"Source: {mode.name} power profile\n"
        f"Current hardware brightness: {brightness_text}\n"
        "Set directly with: settings display set <1-100>\n"
        "Apply profile target with: settings display apply"
    )


def update_display_settings(arguments: str) -> str:
    action, _, value = arguments.strip().partition(" ")
    action = action.casefold()
    value = value.strip()

    if action == "apply" and not value:
        percentage = POWER_PROFILE_MANAGER.get_current_mode().brightness
        result = BACKLIGHT_CONTROLLER.set_percent(percentage)
        return f"Profile brightness target: {result}"

    if action == "set" and value:
        try:
            percentage = int(value)
        except ValueError:
            return "Usage: settings display set <1-100>"
        return BACKLIGHT_CONTROLLER.set_percent(percentage)

    return "Usage: settings display [set <1-100> | apply]"