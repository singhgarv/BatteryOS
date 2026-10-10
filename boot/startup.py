from collections.abc import Callable

from boot.session import SESSION_MANAGER, SessionManager
from power.profile_manager import POWER_PROFILE_MANAGER
from ui.taskbar import Taskbar


class StartupSequence:
    def __init__(
        self,
        taskbar_renderer: Callable[[], str] | None = None,
        session_manager: SessionManager | None = None,
    ):
        self.taskbar_renderer = taskbar_renderer or Taskbar.render
        self.session_manager = session_manager or SESSION_MANAGER

    def run(self) -> list[str]:
        self.session_manager.start()
        return [
            "Battery-First OS startup",
            f"Power profile: {POWER_PROFILE_MANAGER.get_current_mode().name.title()}",
            self.taskbar_renderer(),
            "System ready.",
        ]