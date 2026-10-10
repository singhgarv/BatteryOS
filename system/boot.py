from boot.session import SESSION_MANAGER, SessionManager
from boot.shutdown import ShutdownController
from boot.sleep import SleepController
from boot.startup import StartupSequence


def startup_messages() -> list[str]:
    return StartupSequence().run()


__all__ = [
    "SESSION_MANAGER",
    "SessionManager",
    "ShutdownController",
    "SleepController",
    "StartupSequence",
    "startup_messages",
]