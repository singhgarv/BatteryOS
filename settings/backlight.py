from pathlib import Path


class BacklightController:
    def __init__(self, backlight_root: str | Path = "/sys/class/backlight"):
        self.backlight_root = Path(backlight_root)

    @staticmethod
    def _read_integer(path: Path) -> int | None:
        try:
            return int(path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None

    def _device(self) -> tuple[Path, int] | None:
        try:
            devices = sorted(path for path in self.backlight_root.iterdir() if path.is_dir())
        except OSError:
            return None

        for device in devices:
            maximum = self._read_integer(device / "max_brightness")
            if maximum is not None and maximum > 0:
                return device, maximum
        return None

    def read_percent(self) -> int | None:
        device = self._device()
        if device is None:
            return None
        path, maximum = device
        current = self._read_integer(path / "brightness")
        if current is None:
            return None
        return max(0, min(100, round(current * 100 / maximum)))

    def set_percent(self, percent: int) -> str:
        if not 1 <= percent <= 100:
            return "Brightness must be between 1 and 100 percent."

        device = self._device()
        if device is None:
            return "No controllable backlight was found."

        path, maximum = device
        brightness_path = path / "brightness"
        brightness_value = max(1, round(maximum * percent / 100))
        try:
            brightness_path.write_text(f"{brightness_value}\n", encoding="utf-8")
        except OSError as error:
            return f"Unable to set brightness; check backlight permissions: {error}"
        return f"Brightness set to {percent}% ({brightness_value}/{maximum})."