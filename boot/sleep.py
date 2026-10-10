import platform
import subprocess
from collections.abc import Callable

from boot.session import SESSION_MANAGER, SessionManager


class SleepController:
    def __init__(
        self,
        system_name: str | None = None,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        session_manager: SessionManager | None = None,
    ):
        self.system_name = system_name or platform.system()
        self.runner = runner or subprocess.run
        self.session_manager = session_manager or SESSION_MANAGER

    def request_sleep(self) -> str:
        if self.system_name != "Linux":
            return "Sleep is only supported on Linux."

        self.session_manager.begin_sleep()
        try:
            result = self.runner(
                ["systemctl", "suspend"],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as error:
            self.session_manager.sleep_failed()
            return f"Unable to request sleep: {error}"

        if result.returncode != 0:
            self.session_manager.sleep_failed()
            detail = result.stderr.strip() or f"systemctl exited with status {result.returncode}"
            return f"Unable to request sleep: {detail}"
        self.session_manager.resume()
        return "Sleep request completed; session resumed."