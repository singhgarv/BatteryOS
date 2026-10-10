from dataclasses import dataclass

from config import load_config


@dataclass(frozen=True)
class LaptopProfile:
    cpu_model: str
    memory_gib: int
    graphics: str
    battery_design_wh: float
    battery_health_percent: int
    battery_reserve_percent: int = 25

    @property
    def effective_battery_capacity_wh(self) -> float:
        return round(self.battery_design_wh * self.battery_health_percent / 100, 1)


TARGET_LAPTOP = LaptopProfile(**load_config("defaults.json")["laptop"])