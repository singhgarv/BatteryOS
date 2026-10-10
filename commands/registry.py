from shell.commands import (
    handle_battery,
    handle_browse,
    handle_date,
    handle_help,
    handle_idle,
    handle_open,
    handle_power,
    handle_shutdown,
    handle_sleep,
    handle_status,
    handle_time,
    handle_thermal,
    handle_unknown,
)
from settings.app import handle_settings
from apps.launcher import list_apps
from apps.notes import handle_notes


COMMANDS = {
    "help": handle_help,
    "battery": handle_battery,
    "status": handle_status,
    "time": handle_time,
    "date": handle_date,
    "sleep": handle_sleep,
    "shutdown": handle_shutdown,
}


def resolve_command(command: str):
    return COMMANDS.get(command.lower(), None)


def execute_command(raw_command: str) -> str:
    command = raw_command.strip()
    if not command:
        return ""

    parts = command.split()
    main_command = parts[0].lower()

    if main_command in {"exit", "quit"}:
        return "Goodbye."

    if main_command == "open":
        target = " ".join(parts[1:]) if len(parts) > 1 else ""
        if not target:
            return "Usage: open <app>"
        return handle_open(target)

    if main_command == "power":
        arguments = " ".join(parts[1:])
        return handle_power(arguments)

    if main_command == "idle":
        arguments = " ".join(parts[1:])
        return handle_idle(arguments)

    if main_command == "settings":
        arguments = " ".join(parts[1:])
        return handle_settings(arguments)

    if main_command == "apps":
        if len(parts) != 1:
            return "Usage: apps"
        return list_apps()

    if main_command == "notes":
        arguments = " ".join(parts[1:])
        return handle_notes(arguments)

    if main_command == "browse":
        arguments = command[len(parts[0]):].strip()
        return handle_browse(arguments)

    if main_command == "thermal":
        arguments = " ".join(parts[1:])
        return handle_thermal(arguments)

    handler = resolve_command(main_command)
    if handler is None:
        return handle_unknown(command)
    return handler()
