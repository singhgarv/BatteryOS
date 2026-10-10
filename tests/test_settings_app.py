import unittest
from unittest.mock import patch

from commands.registry import execute_command
from power.profile_manager import POWER_PROFILE_MANAGER
from settings.app import handle_settings, settings_home


class SettingsAppTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_mode = POWER_PROFILE_MANAGER.get_current_mode().name
        self.addCleanup(POWER_PROFILE_MANAGER.set_mode, self.original_mode)

    def test_settings_command_opens_sections_menu(self) -> None:
        self.assertEqual(execute_command("settings"), settings_home())

    def test_open_settings_launches_settings_home(self) -> None:
        self.assertEqual(execute_command("open settings"), settings_home())

    def test_power_settings_selects_shared_profile(self) -> None:
        result = handle_settings("power set performance")

        self.assertEqual(result, "Power mode switched to performance")
        self.assertIn("Power profile: performance", handle_settings("power"))

    def test_sections_use_existing_idle_battery_and_display_data(self) -> None:
        self.assertIn("Automatic idle sleep:", handle_settings("idle status"))
        self.assertIn("Battery level:", handle_settings("battery"))
        self.assertIn("Display brightness target: 35%", handle_settings("display"))
        self.assertIn("Current hardware brightness:", handle_settings("display"))

    def test_network_section_reports_missing_backend(self) -> None:
        self.assertIn("Wi-Fi:", handle_settings("network"))
        self.assertIn("no control backend", handle_settings("network"))

    def test_display_commands_set_brightness_and_apply_profile_target(self) -> None:
        with patch(
            "settings.display.BACKLIGHT_CONTROLLER.set_percent",
            return_value="Brightness set to 55%.",
        ) as set_percent:
            self.assertEqual(handle_settings("display set 55"), "Brightness set to 55%.")
            set_percent.assert_called_once_with(55)

        with patch(
            "settings.display.BACKLIGHT_CONTROLLER.set_percent",
            return_value="Brightness set to 35%.",
        ) as set_percent:
            self.assertEqual(
                handle_settings("display apply"),
                "Profile brightness target: Brightness set to 35%.",
            )
            set_percent.assert_called_once_with(35)


if __name__ == "__main__":
    unittest.main()