import subprocess
import unittest
from unittest.mock import Mock

from boot.session import SessionManager
from boot.shutdown import ShutdownController
from boot.startup import StartupSequence


class StartupSequenceTests(unittest.TestCase):
    def test_startup_loads_taskbar_and_marks_session_running(self) -> None:
        session = SessionManager()
        startup = StartupSequence(
            taskbar_renderer=lambda: "[Battery 50%]", session_manager=session
        )

        messages = startup.run()

        self.assertEqual(messages[0], "Battery-First OS startup")
        self.assertIn("[Battery 50%]", messages)
        self.assertEqual(messages[-1], "System ready.")
        self.assertEqual(session.state, "running")


class ShutdownControllerTests(unittest.TestCase):
    def test_linux_shutdown_calls_systemctl_and_marks_session(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["systemctl", "poweroff"], returncode=0, stderr=""
            )
        )
        session = SessionManager()
        controller = ShutdownController(
            system_name="Linux", runner=runner, session_manager=session
        )

        result = controller.request_shutdown()

        self.assertEqual(result, "Shutdown request sent.")
        self.assertEqual(session.state, "shutting down")
        runner.assert_called_once_with(
            ["systemctl", "poweroff"], check=False, capture_output=True, text=True
        )

    def test_non_linux_shutdown_never_runs_system_command(self) -> None:
        runner = Mock()
        controller = ShutdownController(system_name="Windows", runner=runner)

        result = controller.request_shutdown()

        self.assertEqual(result, "Shutdown is only supported on Linux.")
        runner.assert_not_called()

    def test_shutdown_failure_keeps_session_open(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["systemctl", "poweroff"], returncode=1, stderr="not authorized"
            )
        )
        session = SessionManager()
        controller = ShutdownController(
            system_name="Linux", runner=runner, session_manager=session
        )

        self.assertEqual(
            controller.request_shutdown(), "Unable to request shutdown: not authorized"
        )
        self.assertEqual(session.state, "stopped")


if __name__ == "__main__":
    unittest.main()