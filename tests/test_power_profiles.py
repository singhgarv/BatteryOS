import unittest

from commands.registry import execute_command
from power.modes import POWER_MODES
from power.profile_manager import POWER_PROFILE_MANAGER, PowerProfileManager
from shell.router import route_command
from ui.stats import get_system_stats


class PowerProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_mode = POWER_PROFILE_MANAGER.get_current_mode().name
        self.addCleanup(POWER_PROFILE_MANAGER.set_mode, self.original_mode)

    def test_profile_names_are_normalized(self) -> None:
        manager = PowerProfileManager()

        result = manager.set_mode("  BATTERY-SAVER ")

        self.assertEqual(result, "Power mode switched to battery saver")
        self.assertEqual(manager.get_current_mode().name, "battery saver")

    def test_policy_values_come_from_profile_definition(self) -> None:
        manager = PowerProfileManager("balanced")
        mode = POWER_MODES["balanced"]

        self.assertEqual(
            manager.get_current_policy(),
            {
                "brightness": mode.brightness,
                "cpu_limit": mode.cpu_limit,
                "idle_timeout": mode.idle_timeout,
                "background": mode.background_service_policy,
            },
        )

    def test_shell_selects_and_reports_shared_profile(self) -> None:
        response = route_command("power set balanced")

        self.assertEqual(response, "Power mode switched to balanced")
        self.assertIn("Mode: balanced", execute_command("status"))
        self.assertEqual(get_system_stats()["power_mode"], "Balanced")

    def test_unknown_profile_does_not_change_current_mode(self) -> None:
        POWER_PROFILE_MANAGER.set_mode("balanced")

        response = route_command("power set turbo")

        self.assertEqual(response, "Unknown mode: turbo")
        self.assertEqual(POWER_PROFILE_MANAGER.get_current_mode().name, "balanced")

    def test_power_list_marks_current_profile(self) -> None:
        POWER_PROFILE_MANAGER.set_mode("performance")

        response = route_command("power list")

        self.assertIn("* performance", response)
        self.assertIn(" battery saver", response)


if __name__ == "__main__":
    unittest.main()