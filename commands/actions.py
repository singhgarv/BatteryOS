from apps.notes import handle_notes
from apps.browser import BROWSER_APP


def launch_chrome(target: str = "") -> str:
    return BROWSER_APP.open(target, browser_name="chrome")


def launch_settings() -> str:
    from settings.app import settings_home

    return settings_home()


def launch_notes() -> str:
    return handle_notes()


def launch_terminal() -> str:
    return "You are already in the Battery OS terminal."


def launch_browser(target: str = "") -> str:
    return BROWSER_APP.open(target, browser_name=None)


def launch_diagnostics() -> str:
    from shell.commands import handle_status

    return handle_status()


APP_ACTIONS = {
    "chrome": launch_chrome,
    "browser": launch_browser,
    "settings": launch_settings,
    "notes": launch_notes,
    "terminal": launch_terminal,
    "diagnostics": launch_diagnostics,
}

APP_ALIASES = {
    "system settings": "settings",
    "notepad": "notes",
    "web browser": "browser",
}


def launch_app(app_name: str) -> str:
    key = app_name.strip().casefold()
    key = APP_ALIASES.get(key, key)
    action = APP_ACTIONS.get(key)
    if action is None:
        return f"Unknown app: {app_name}."
    return action()
