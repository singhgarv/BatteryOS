from settings.battery import show_battery_settings
from settings.display import show_display_settings, update_display_settings
from settings.network import show_network_settings
from settings.power import show_power_settings, update_power_settings


def settings_home() -> str:
    return (
        "Settings\n"
        "power    Power profiles\n"
        "idle     Idle and sleep timeout\n"
        "battery  Battery health and runtime\n"
        "display  Brightness control\n"
        "network  Network availability\n"
        "Open a section with: settings <section>"
    )


def handle_settings(arguments: str = "") -> str:
    section, _, options = arguments.strip().partition(" ")
    section = section.casefold()
    options = options.strip()

    if not section:
        return settings_home()
    if section == "power":
        if not options:
            return show_power_settings()
        return update_power_settings(options)
    if section == "idle":
        from shell.commands import handle_idle

        return handle_idle(options)
    if section == "battery" and not options:
        return show_battery_settings()
    if section == "display":
        if not options:
            return show_display_settings()
        return update_display_settings(options)
    if section == "network" and not options:
        return show_network_settings()
    if section in {"power", "idle", "battery", "display", "network"}:
        return f"Usage: settings {section}"
    return "Usage: settings [power | idle | battery | display | network]"