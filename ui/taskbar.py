from .render import render_taskbar
from .stats import get_system_stats


class Taskbar:
    @staticmethod
    def render() -> str:
        return render_taskbar(get_system_stats())

    @staticmethod
    def render_with_stats(stats: dict) -> str:
        return render_taskbar(stats)
