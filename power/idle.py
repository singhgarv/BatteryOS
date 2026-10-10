from collections.abc import Callable
from time import monotonic

from .profile_manager import POWER_PROFILE_MANAGER


class IdleController:
    def __init__(self, timeout_provider: Callable[[], int], clock: Callable[[], float] = monotonic):
        self._timeout_provider = timeout_provider
        self._clock = clock
        self._timeout_override: int | None = None
        self._last_activity = clock()

    @property
    def timeout_override(self) -> int | None:
        return self._timeout_override

    @property
    def timeout_seconds(self) -> int:
        if self._timeout_override is not None:
            return self._timeout_override
        return max(0, self._timeout_provider())

    @property
    def seconds_until_idle(self) -> float | None:
        timeout = self.timeout_seconds
        if timeout == 0:
            return None
        elapsed = self._clock() - self._last_activity
        return max(0.0, timeout - elapsed)

    @property
    def is_idle(self) -> bool:
        remaining = self.seconds_until_idle
        return remaining is not None and remaining <= 0

    def record_activity(self) -> None:
        self._last_activity = self._clock()

    def set_timeout(self, seconds: int) -> None:
        if not 0 <= seconds <= 86_400:
            raise ValueError("Idle timeout must be between 0 and 86400 seconds")
        self._timeout_override = seconds
        self.record_activity()

    def follow_profile(self) -> None:
        self._timeout_override = None
        self.record_activity()


IDLE_CONTROLLER = IdleController(
    lambda: POWER_PROFILE_MANAGER.get_current_mode().idle_timeout
)