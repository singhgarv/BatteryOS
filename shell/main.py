import os
import select
import sys

if __package__ in (None, ""):
    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from shell.router import route_command
else:
    from .router import route_command

from power.idle import IDLE_CONTROLLER
from system.boot import SleepController, StartupSequence


def _read_command(prompt: str) -> tuple[str | None, bool]:
    if not sys.stdin.isatty():
        try:
            return input(prompt), False
        except EOFError:
            return None, False

    print(prompt, end="", flush=True)
    try:
        readable, _, _ = select.select(
            [sys.stdin], [], [], IDLE_CONTROLLER.seconds_until_idle
        )
    except (OSError, ValueError):
        try:
            return input(), False
        except EOFError:
            return None, False
    if not readable:
        return None, True

    command = sys.stdin.readline()
    if not command:
        return None, False
    return command.rstrip("\r\n"), False


def main() -> None:
    for startup_message in StartupSequence().run():
        print(startup_message)
    print("Type 'help' to see available commands.")
    idle_controller = IDLE_CONTROLLER
    sleep_controller = SleepController()
    idle_controller.record_activity()

    while True:
        try:
            raw_command, idle_timeout = _read_command("user@battery-os:~$ ")
        except KeyboardInterrupt:
            print("\nSession interrupted.")
            break

        if idle_timeout:
            print(f"\nIdle timeout reached ({idle_controller.timeout_seconds}s).")
            print(sleep_controller.request_sleep())
            idle_controller.record_activity()
            continue

        if raw_command is None:
            print("\nGoodbye.")
            break

        command = raw_command.strip()
        if not command:
            idle_controller.record_activity()
            continue

        if command.lower() in {"exit", "quit"}:
            print("Goodbye.")
            break

        result = route_command(command)
        if result:
            print(result)
        if result == "Shutdown request sent.":
            break
        idle_controller.record_activity()


if __name__ == "__main__":
    main()
