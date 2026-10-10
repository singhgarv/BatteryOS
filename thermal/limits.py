from dataclasses import dataclass


@dataclass(frozen=True)
class ThermalLimits:
    warm_c: float = 70.0
    hot_c: float = 85.0
    critical_c: float = 95.0

    def __post_init__(self) -> None:
        if not 0 < self.warm_c < self.hot_c < self.critical_c <= 150:
            raise ValueError("Thermal limits must increase from warm to critical and stay at or below 150 C")

    def classify(self, temperature_c: float) -> str:
        if temperature_c >= self.critical_c:
            return "critical"
        if temperature_c >= self.hot_c:
            return "hot"
        if temperature_c >= self.warm_c:
            return "warm"
        return "normal"

    def recommended_profile(self, state: str, current_profile: str) -> str:
        if state in {"hot", "critical"}:
            return "battery saver"
        if state == "warm" and current_profile == "performance":
            return "balanced"
        return current_profile