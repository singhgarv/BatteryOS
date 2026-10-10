from pathlib import Path


class BatterySensor:
    def __init__(
        self,
        level: int | None = None,
        health: int | None = None,
        charging: bool | None = None,
        *,
        power_supply_path: str | Path = "/sys/class/power_supply",
    ):
        self.level = level
        self.health = health
        self.charging = charging
        self.power_supply_path = Path(power_supply_path)

    @staticmethod
    def _read_text(path: Path) -> str | None:
        try:
            return path.read_text(encoding="utf-8").strip()
        except OSError:
            return None

    @classmethod
    def _read_value(cls, path: Path) -> int | None:
        value = cls._read_text(path)
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _percentage(current: int | None, full: int | None) -> int | None:
        if current is None or full is None or full <= 0:
            return None
        return max(0, min(100, round(current * 100 / full)))

    def _battery_paths(self) -> list[Path]:
        try:
            paths = sorted(self.power_supply_path.iterdir())
        except OSError:
            return []
        return [path for path in paths if self._read_text(path / "type") == "Battery"]

    def _external_power_supplies(self) -> list[dict[str, int | str | None]]:
        try:
            paths = sorted(self.power_supply_path.iterdir())
        except OSError:
            return []

        supplies = []
        for path in paths:
            supply_type = self._read_text(path / "type")
            if supply_type is None or supply_type.casefold() == "battery":
                continue
            online = self._read_value(path / "online")
            if online in {0, 1}:
                supplies.append({"name": path.name, "type": supply_type, "online": online == 1})
        return supplies

    def _read_battery(self, path: Path) -> dict:
        energy_now = self._read_value(path / "energy_now")
        energy_full = self._read_value(path / "energy_full")
        energy_design = self._read_value(path / "energy_full_design")
        charge_now = self._read_value(path / "charge_now")
        charge_full = self._read_value(path / "charge_full")
        charge_design = self._read_value(path / "charge_full_design")
        voltage_now = self._read_value(path / "voltage_now")
        current_now = self._read_value(path / "current_now")
        power_now = self._read_value(path / "power_now")

        level = self._percentage(energy_now, energy_full)
        level_provenance = "calculated_estimate" if level is not None else None
        if level is None:
            level = self._percentage(charge_now, charge_full)
            if level is not None:
                level_provenance = "calculated_estimate"
        if level is None:
            level = self._read_value(path / "capacity")
            if level is not None:
                level = max(0, min(100, level))
                level_provenance = "kernel_reported"

        health = self._percentage(energy_full, energy_design)
        if health is None:
            health = self._percentage(charge_full, charge_design)

        if energy_now is not None:
            remaining_energy_wh = max(0, energy_now) / 1_000_000
        elif charge_now is not None and voltage_now is not None:
            remaining_energy_wh = max(0, charge_now * voltage_now) / 1_000_000_000_000
        else:
            remaining_energy_wh = None

        if power_now is not None:
            power_w = abs(power_now) / 1_000_000
        elif current_now is not None and voltage_now is not None:
            power_w = abs(current_now * voltage_now) / 1_000_000_000_000
        else:
            power_w = None

        status = (self._read_text(path / "status") or "").lower()
        if status == "charging":
            charging = True
        elif status in {"discharging", "full", "not charging"}:
            charging = False
        else:
            charging = None

        energy_now_wh = energy_now / 1_000_000 if energy_now is not None else None
        energy_full_wh = energy_full / 1_000_000 if energy_full is not None else None
        energy_design_wh = energy_design / 1_000_000 if energy_design is not None else None
        if energy_now_wh is None and charge_now is not None and voltage_now is not None:
            energy_now_wh = charge_now * voltage_now / 1_000_000_000_000
        if energy_full_wh is None and charge_full is not None and voltage_now is not None:
            energy_full_wh = charge_full * voltage_now / 1_000_000_000_000
        if energy_design_wh is None and charge_design is not None and voltage_now is not None:
            energy_design_wh = charge_design * voltage_now / 1_000_000_000_000

        measurement_provenance = {
            "battery_level": level_provenance,
            "battery_health": "calculated_estimate" if health is not None else None,
            "energy_now_wh": (
                "kernel_reported" if energy_now is not None
                else "calculated_estimate" if energy_now_wh is not None
                else None
            ),
            "energy_full_wh": (
                "kernel_reported" if energy_full is not None
                else "calculated_estimate" if energy_full_wh is not None
                else None
            ),
            "energy_design_wh": (
                "kernel_reported" if energy_design is not None
                else "calculated_estimate" if energy_design_wh is not None
                else None
            ),
            "voltage_v": "kernel_reported" if voltage_now is not None else None,
            "current_a": "kernel_reported" if current_now is not None else None,
            "power_w": (
                "kernel_reported" if power_now is not None
                else "calculated_estimate" if power_w is not None
                else None
            ),
            "charging": "kernel_reported" if status else None,
        }

        return {
            "name": path.name,
            "status": status or "unknown",
            "level": level,
            "health": health,
            "charging": charging,
            "remaining_energy_wh": remaining_energy_wh,
            "energy_now_wh": energy_now_wh,
            "energy_full_wh": energy_full_wh,
            "energy_design_wh": energy_design_wh,
            "voltage_v": voltage_now / 1_000_000 if voltage_now is not None else None,
            "current_a": current_now / 1_000_000 if current_now is not None else None,
            "power_w": power_w,
            "discharge_rate_w": power_w if status == "discharging" else None,
            "energy_now_uwh": energy_now,
            "energy_full_uwh": energy_full,
            "energy_design_uwh": energy_design,
            "charge_now_uah": charge_now,
            "charge_full_uah": charge_full,
            "charge_design_uah": charge_design,
            "voltage_uv": voltage_now,
            "current_ua": current_now,
            "power_uw": power_now,
            "measurement_provenance": measurement_provenance,
        }

    @staticmethod
    def _average(batteries: list[dict], key: str) -> int | None:
        values = [battery[key] for battery in batteries if battery[key] is not None]
        if not values:
            return None
        return round(sum(values) / len(values))

    @staticmethod
    def _charging_state(batteries: list[dict]) -> bool | None:
        states = [battery["charging"] for battery in batteries if battery["charging"] is not None]
        if any(states):
            return True
        if states:
            return False
        return None

    @staticmethod
    def _estimate_runtime(batteries: list[dict], charging: bool | None) -> float | None:
        if charging is True:
            return None
        energy = [battery["remaining_energy_wh"] for battery in batteries if battery["remaining_energy_wh"] is not None]
        power = [battery["power_w"] for battery in batteries if battery["power_w"] is not None]
        total_power = sum(power)
        if not energy or total_power <= 0:
            return None
        return round(sum(energy) / total_power, 2)

    def read_level(self) -> int | None:
        if self.level is not None:
            return self.level
        return self._average([self._read_battery(path) for path in self._battery_paths()], "level")

    def read_health(self) -> int | None:
        if self.health is not None:
            return self.health
        return self._average([self._read_battery(path) for path in self._battery_paths()], "health")

    def is_charging(self) -> bool | None:
        if self.charging is not None:
            return self.charging
        batteries = [self._read_battery(path) for path in self._battery_paths()]
        return self._charging_state(batteries)

    def estimate_runtime_hours(self) -> float | None:
        batteries = [self._read_battery(path) for path in self._battery_paths()]
        charging = self.charging if self.charging is not None else self._charging_state(batteries)
        return self._estimate_runtime(batteries, charging)

    def get_status(self) -> dict[str, int | bool | float | None]:
        batteries = [self._read_battery(path) for path in self._battery_paths()]
        charging = self.charging if self.charging is not None else self._charging_state(batteries)
        external_supplies = self._external_power_supplies()
        online_states = [supply["online"] for supply in external_supplies]
        ac_connected = True if any(online_states) else False if online_states else None
        external_energy = lambda key: sum(
            battery[key] for battery in batteries if battery[key] is not None
        ) or None
        return {
            "battery_level": self.level if self.level is not None else self._average(batteries, "level"),
            "battery_health": self.health if self.health is not None else self._average(batteries, "health"),
            "charging": charging,
            "estimated_runtime_hours": self._estimate_runtime(batteries, charging),
            "ac_connected": ac_connected,
            "power_source": "ac" if ac_connected is True else "battery" if ac_connected is False else "unknown",
            "batteries": batteries,
            "external_power_supplies": external_supplies,
            "energy_now_wh": external_energy("energy_now_wh"),
            "energy_full_wh": external_energy("energy_full_wh"),
            "energy_design_wh": external_energy("energy_design_wh"),
            "discharge_rate_w": sum(
                battery["discharge_rate_w"]
                for battery in batteries
                if battery["discharge_rate_w"] is not None
            ) or None,
            "measurement_provenance": {
                "battery_level": "kernel_reported" if self.level is not None else next(
                    (battery["measurement_provenance"]["battery_level"] for battery in batteries
                     if battery["measurement_provenance"]["battery_level"] is not None),
                    None,
                ),
                "battery_health": "kernel_reported" if self.health is not None else "calculated_estimate" if any(
                    battery["measurement_provenance"]["battery_health"] is not None for battery in batteries
                ) else None,
                "energy_now_wh": "kernel_reported" if any(battery["energy_now_uwh"] is not None for battery in batteries)
                else "calculated_estimate" if external_energy("energy_now_wh") is not None else None,
                "energy_full_wh": "kernel_reported" if any(battery["energy_full_uwh"] is not None for battery in batteries)
                else "calculated_estimate" if external_energy("energy_full_wh") is not None else None,
                "energy_design_wh": "kernel_reported" if any(battery["energy_design_uwh"] is not None for battery in batteries)
                else "calculated_estimate" if external_energy("energy_design_wh") is not None else None,
                "ac_connected": "kernel_reported" if online_states else None,
            },
        }
