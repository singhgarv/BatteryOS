import unittest
from unittest.mock import Mock, patch

from commands.registry import execute_command
from power.automatic import BatteryAwarePowerPolicy
from power.laptop_profile import TARGET_LAPTOP
from power.profile_manager import PowerProfileManager


class BatteryAwarePowerPolicyTests(unittest.TestCase):
    def make_policy(
        self,
        *,
        charging: bool | None,
        level: int | None = 80,
        health: int | None = 64,
        thermal_state: str = "normal",
        current_profile: str = "balanced",
        applied: bool = True,
    ) -> tuple[BatteryAwarePowerPolicy, PowerProfileManager, Mock]:
        battery = Mock()
        battery.get_status.return_value = {
            "charging": charging,
            "battery_level": level,
            "battery_health": health,
        }
        thermal = Mock()
        thermal.get_status.return_value = {"state": thermal_state}
        profile_manager = PowerProfileManager(current_profile)
        backend = Mock()
        backend.apply.return_value = (applied, "profile backend result")
        policy = BatteryAwarePowerPolicy(
            battery_sensor=battery,
            thermal_manager=thermal,
            profile_manager=profile_manager,
            backend=backend,
        )
        return policy, profile_manager, backend

    def test_laptop_profile_uses_documented_capacity_and_health(self) -> None:
        self.assertEqual(TARGET_LAPTOP.effective_battery_capacity_wh, 25.0)
        self.assertEqual(TARGET_LAPTOP.battery_reserve_percent, 25)

    def test_battery_power_prefers_saver_for_weak_battery(self) -> None:
        policy, _, _ = self.make_policy(charging=False, current_profile="performance")

        recommendation = policy.recommend()

        self.assertEqual(recommendation["recommended_profile"], "battery saver")
        self.assertIn("64%", recommendation["reason"])

    def test_low_reserve_recommends_saver(self) -> None:
        policy, _, _ = self.make_policy(charging=False, level=20)

        self.assertIn("25% reserve", policy.recommend()["reason"])

    def test_plugged_in_cool_performance_is_allowed(self) -> None:
        policy, _, _ = self.make_policy(
            charging=True, thermal_state="normal", current_profile="performance"
        )

        self.assertEqual(policy.recommend()["recommended_profile"], "performance")

    def test_hot_thermal_state_overrides_performance(self) -> None:
        policy, _, _ = self.make_policy(
            charging=True, thermal_state="hot", current_profile="performance"
        )

        self.assertEqual(policy.recommend()["recommended_profile"], "battery saver")

    def test_unknown_power_source_uses_conservative_profile(self) -> None:
        policy, _, _ = self.make_policy(charging=None, current_profile="balanced")

        self.assertEqual(policy.recommend()["recommended_profile"], "battery saver")

    def test_apply_updates_selected_profile_only_after_backend_success(self) -> None:
        policy, profile_manager, backend = self.make_policy(
            charging=False, current_profile="performance", applied=True
        )

        policy.apply_recommendation()

        self.assertEqual(profile_manager.get_current_mode().name, "battery saver")
        backend.apply.assert_called_once_with("battery saver")

        policy, profile_manager, _ = self.make_policy(
            charging=False, current_profile="performance", applied=False
        )
        policy.apply_recommendation()
        self.assertEqual(profile_manager.get_current_mode().name, "performance")

    def test_power_auto_command_routes_status_and_apply(self) -> None:
        policy = Mock()
        policy.format_recommendation.return_value = "Recommended profile: battery saver"
        policy.apply_recommendation.return_value = "Applied Linux power profile: power-saver."

        with patch("shell.commands.LAPTOP_POWER_POLICY", policy):
            self.assertEqual(
                execute_command("power auto"), "Recommended profile: battery saver"
            )
            self.assertEqual(
                execute_command("power auto apply"),
                "Applied Linux power profile: power-saver.",
            )


if __name__ == "__main__":
    unittest.main()