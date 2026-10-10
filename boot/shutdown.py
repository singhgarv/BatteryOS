import platform
import subprocess
from collections.abc import Callable

from boot.session import SESSION_MANAGER, SessionManager


class ShutdownController:
    def __init__(
        self,
        system_name: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        session_manager: SessionManager | None = None,
    ):
        self.system_name = system_name or platform.system()
        self.runner = runner or subprocess.run
        self.session_manager = session_manager or SESSION_MANAGER

    def request_shutdown(self) -> str:
        if self.system_name != "Linux":
            return "Shutdown is only supported on Linux."

        try:
            result = self.runner(
                ["systemctl", "poweroff"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            return f"Unable to request shutdown: {error}"

        if result.returncode != 0:
            detail = result.stderr.strip() or f"systemctl exited with status {result.returncode}"
            return f"Unable to request shutdown: {detail}"

        self.session_manager.begin_shutdown()
        return "Shutdown request sent."