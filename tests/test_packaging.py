import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

from config import load_config
from power.laptop_profile import TARGET_LAPTOP
from power.modes import POWER_MODES
from power.profile_manager import PowerProfileManager
from system.boot import SessionManager, StartupSequence
from system.status import get_system_status, render_system_status
from scripts.build_ubuntu_live_image import build_image, prepare_build_tree


class PackagingTests(unittest.TestCase):
    def test_json_configuration_drives_power_and_laptop_defaults(self) -> None:
        profiles = load_config("power_profiles.json")
        defaults = load_config("defaults.json")

        self.assertEqual(POWER_MODES["battery saver"].cpu_limit, profiles["battery saver"]["cpu_limit"])
        self.assertEqual(PowerProfileManager().get_current_mode().name, defaults["power"]["default_profile"])
        self.assertEqual(TARGET_LAPTOP.effective_battery_capacity_wh, 25.0)

    def test_system_status_facade_reports_existing_runtime_state(self) -> None:
        status = get_system_status()

        self.assertEqual(status["state"], "active")
        self.assertIn("System status: active", render_system_status())
        self.assertIn("Thermal state:", render_system_status())

    def test_system_boot_facade_reuses_startup_sequence(self) -> None:
        session = SessionManager()
        startup = StartupSequence(
            taskbar_renderer=lambda: "taskbar", session_manager=session
        )

        messages = startup.run()

        self.assertIn("taskbar", messages)
        self.assertEqual(session.state, "running")

    def test_root_runtime_delegates_to_existing_shell(self) -> None:
        with patch("shell.main.main") as shell_main:
            from runtime import run

            run()

        shell_main.assert_called_once_with()

    def test_live_image_staging_includes_app_but_excludes_tests(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory:
            build_directory = prepare_build_tree(
                repository_root, Path(temporary_directory) / "image-build"
            )
            staged_app = build_directory / "config" / "includes.chroot" / "opt" / "battery-os"

            self.assertTrue((staged_app / "main.py").is_file())
            self.assertTrue((staged_app / "config" / "defaults.json").is_file())
            self.assertFalse((staged_app / "tests").exists())
            self.assertTrue(
                (build_directory / "config" / "package-lists" / "battery-os.list.chroot").is_file()
            )

    def test_live_image_build_is_linux_root_only(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "from Linux"):
            build_image(system_name="Windows", effective_uid=0)

    def test_live_image_driver_configures_then_builds(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary_directory, patch(
            "scripts.build_ubuntu_live_image.shutil.which", return_value="/usr/bin/lb"
        ):
            runner = unittest.mock.Mock()
            build_image(
                repository_root,
                Path(temporary_directory) / "image-build",
                system_name="Linux",
                effective_uid=0,
                runner=runner,
            )

        self.assertEqual(runner.call_count, 2)
        self.assertIn("noble", runner.call_args_list[0].args[0])
        self.assertIn("iso-hybrid", runner.call_args_list[0].args[0])
        self.assertIn("persistent", runner.call_args_list[0].args[0])
        self.assertIn("false", runner.call_args_list[0].args[0])
        self.assertEqual(runner.call_args_list[1].args[0][-1], "build")


if __name__ == "__main__":
    unittest.main()