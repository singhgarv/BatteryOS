from datetime import datetime

from sensors.battery import BatterySensor
from sensors.charging import charging_state
from sensors.health import battery_health_status
from power.profile_manager import POWER_PROFILE_MANAGER
from power.idle import IDLE_CONTROLLER
from boot.sleep import SleepController
from boot.shutdown import ShutdownController
from thermal.manager import THERMAL_MANAGER
from power.automatic import LAPTOP_POWER_POLICY
from system.status import render_system_status

SLEEP_CONTROLLER = SleepController()
SHUTDOWN_CONTROLLER = ShutdownController()


def handle_help() -> str:
    try:
        from .help import get_help_text
    except ImportError:
        from help import get_help_text
    return get_help_text()


def handle_battery() -> str:
    status = BatterySensor().get_status()
    level = status["battery_level"]
    health = status["battery_health"]
    runtime = status["estimated_runtime_hours"]
    power_mode = POWER_PROFILE_MANAGER.get_current_mode().name
    health_text = "unknown"
    if health is not None:
        health_text = f"{health}% ({battery_health_status(health)})"
    level_text = f"{level}%" if level is not None else "unknown"
    runtime_text = "unknown"
    if runtime is not None:
        minutes = round(runtime * 60)
        runtime_text = f"{minutes // 60}h {minutes % 60:02d}m"

    return (
        f"Battery health: {health_text}\n"
        f"Battery remaining: {level_text}\n"
        f"Charging: {charging_state(status['charging'])}\n"
        f"Power mode: {power_mode}\n"
        f"Estimated runtime: {runtime_text}"
    )


def handle_status() -> str:
    return render_system_status()


def handle_power(arguments: str = "") -> str:
    action, _, target = arguments.strip().partition(" ")
    action = action.casefold()
    target = target.strip()

    if not action:
        return f"Current power profile:\n{POWER_PROFILE_MANAGER.describe_current()}"

    if action == "list" and not target:
        modes = POWER_PROFILE_MANAGER.list_modes()
        current_mode = POWER_PROFILE_MANAGER.get_current_mode().name
        entries = [
            f"{'*' if mode.name == current_mode else ' '} {mode.name}"
            for mode in modes
        ]
        return "Available power profiles:\n" + "\n".join(entries)

    if action == "show" and target:
        mode = POWER_PROFILE_MANAGER.get_mode(target)
        if mode is None:
            return f"Unknown power profile: {target}"
        return mode.describe()

    if action == "set" and target:
        return POWER_PROFILE_MANAGER.set_mode(target)

    if action == "auto":
        if target in {"", "status"}:
            return LAPTOP_POWER_POLICY.format_recommendation()
        if target == "apply":
            return LAPTOP_POWER_POLICY.apply_recommendation()
        return "Usage: power auto [status | apply]"

    return "Usage: power [list | show <profile> | set <profile> | auto [status | apply]]"


def handle_idle(arguments: str = "") -> str:
    action, _, value = arguments.strip().partition(" ")
    action = action.casefold()
    value = value.strip()

    if not action or action == "status" and not value:
        timeout = IDLE_CONTROLLER.timeout_seconds
        if timeout == 0:
            return "Automatic idle sleep is disabled."
        if IDLE_CONTROLLER.timeout_override is None:
            profile = POWER_PROFILE_MANAGER.get_current_mode().name
            source = f"{profile} profile"
        else:
            source = "custom timeout"
        return f"Automatic idle sleep: {timeout} seconds ({source})."

    if action == "set" and value:
        try:
            timeout = int(value)
            IDLE_CONTROLLER.set_timeout(timeout)
        except ValueError as error:
            return str(error) if value.isdecimal() else "Usage: idle set <seconds>"
        return f"Idle timeout set to {timeout} seconds."

    if action == "off" and not value:
        IDLE_CONTROLLER.set_timeout(0)
        return "Automatic idle sleep is disabled."

    if action == "profile" and not value:
        IDLE_CONTROLLER.follow_profile()
        timeout = IDLE_CONTROLLER.timeout_seconds
        profile = POWER_PROFILE_MANAGER.get_current_mode().name
        return f"Idle timeout follows the {profile} profile: {timeout} seconds."

    return "Usage: idle [status | set <seconds> | off | profile]"


def handle_time() -> str:
    return datetime.now().strftime("%I:%M:%S %p")


def handle_date() -> str:
    return datetime.now().strftime("%A, %B %d, %Y")


def handle_sleep() -> str:
    return SLEEP_CONTROLLER.request_sleep()


def handle_shutdown() -> str:
    return SHUTDOWN_CONTROLLER.request_shutdown()


def handle_open(target: str) -> str:
    from apps.launcher import open_app

    return open_app(target)


def handle_browse(target: str = "") -> str:
    if not target.strip():
        return "Usage: browse <url>"
    from commands.actions import launch_browser

    return launch_browser(target.strip())


def handle_thermal(arguments: str = "") -> str:
    action = arguments.strip().casefold()
    if not action or action == "status":
        return THERMAL_MANAGER.format_status()
    if action == "tune":
        return THERMAL_MANAGER.apply_recommended_profile()
    return "Usage: thermal [status | tune]"


def handle_unknown(command: str) -> str:
    return f"Unknown command: {command}. Type 'help' for available commands."
