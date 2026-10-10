import subprocess
import unittest
from unittest.mock import Mock

from boot.sleep import SleepController
from boot.session import SessionManager
from power.idle import IDLE_CONTROLLER, IdleController
from power.profile_manager import PowerProfileManager
from shell.commands import handle_idle


class IdleControllerTests(unittest.TestCase):
    def test_timeout_tracks_active_profile_and_activity(self) -> None:
        now = [100.0]
        manager = PowerProfileManager("battery saver")
        controller = IdleController(
            lambda: manager.get_current_mode().idle_timeout,
            clock=lambda: now[0],
        )

        self.assertEqual(controller.seconds_until_idle, 30)
        now[0] += 10
        manager.set_mode("balanced")
        self.assertEqual(controller.seconds_until_idle, 80)

        controller.record_activity()

        self.assertEqual(controller.seconds_until_idle, 90)

    def test_timeout_can_be_overridden_or_disabled(self) -> None:
        now = [0.0]
        controller = IdleController(lambda: 30, clock=lambda: now[0])

        controller.set_timeout(5)
        now[0] += 5
        self.assertTrue(controller.is_idle)

        controller.set_timeout(0)
        self.assertIsNone(controller.seconds_until_idle)
        self.assertFalse(controller.is_idle)

        controller.follow_profile()
        self.assertEqual(controller.timeout_seconds, 30)

    def test_rejects_out_of_range_timeout(self) -> None:
        controller = IdleController(lambda: 30)

        with self.assertRaises(ValueError):
            controller.set_timeout(86_401)


class SleepControllerTests(unittest.TestCase):
    def test_linux_sleep_calls_systemctl_suspend(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["systemctl", "suspend"], returncode=0, stderr=""
            )
        )
        session = SessionManager()
        controller = SleepController(system_name="Linux", runner=runner, session_manager=session)

        result = controller.request_sleep()

        self.assertEqual(result, "Sleep request completed; session resumed.")
        self.assertEqual(session.state, "running")
        self.assertEqual(session.sleep_count, 1)
        self.assertEqual(session.resume_count, 1)
        runner.assert_called_once_with(
            ["systemctl", "suspend"], check=False, capture_output=True, text=True
        )

    def test_non_linux_sleep_is_rejected_without_running_command(self) -> None:
        runner = Mock()
        controller = SleepController(system_name="Windows", runner=runner)

        result = controller.request_sleep()

        self.assertEqual(result, "Sleep is only supported on Linux.")
        runner.assert_not_called()

    def test_reports_systemctl_failure(self) -> None:
        runner = Mock(
            return_value=subprocess.CompletedProcess(
                args=["systemctl", "suspend"], returncode=1, stderr="not authorized"
            )
        )
        session = SessionManager()
        controller = SleepController(system_name="Linux", runner=runner, session_manager=session)

        self.assertEqual(
            controller.request_sleep(), "Unable to request sleep: not authorized"
        )
        self.assertEqual(session.state, "running")


class IdleCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_override = IDLE_CONTROLLER.timeout_override
        self.addCleanup(self.restore_timeout)

    def restore_timeout(self) -> None:
        if self.original_override is None:
            IDLE_CONTROLLER.follow_profile()
        else:
            IDLE_CONTROLLER.set_timeout(self.original_override)

    def test_idle_timeout_can_be_set_disabled_and_reset_to_profile(self) -> None:
        self.assertEqual(handle_idle("set 45"), "Idle timeout set to 45 seconds.")
        self.assertIn("45 seconds (custom timeout)", handle_idle("status"))
        self.assertEqual(handle_idle("off"), "Automatic idle sleep is disabled.")
        self.assertEqual(handle_idle("profile").split(": ")[1].split(" seconds")[0], "30")


if __name__ == "__main__":
    unittest.main()