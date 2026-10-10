import webbrowser
from collections.abc import Callable
from urllib.parse import urlsplit, urlunsplit


BrowserOpener = Callable[[str, str | None], bool]


def normalize_url(target: str) -> str | None:
    value = target.strip()
    if not value or any(character.isspace() for character in value):
        return None
    if "://" not in value:
        value = f"https://{value}"

    try:
        parsed = urlsplit(value)
        if parsed.scheme.casefold() not in {"http", "https"} or not parsed.hostname:
            return None
        if parsed.username is not None or parsed.password is not None:
            return None
        parsed.port
    except ValueError:
        return None

    return urlunsplit(parsed)


def _open_in_browser(url: str, browser_name: str | None) -> bool:
    browser = webbrowser.get(browser_name) if browser_name else webbrowser
    return browser.open_new_tab(url)


class BrowserApp:
    def __init__(self, opener: BrowserOpener | None = None):
        self._opener = opener or _open_in_browser

    def open(self, target: str = "", browser_name: str | None = None) -> str:
        url = "about:blank" if not target.strip() else normalize_url(target)
        if url is None:
            return "Invalid URL. Use an http or https address."

        try:
            opened = self._opener(url, browser_name)
        except webbrowser.Error as error:
            browser_label = "Chrome" if browser_name else "default browser"
            return f"Unable to open {browser_label}: {error}"
        except OSError as error:
            return f"Unable to open browser: {error}"

        if not opened:
            return "No browser could be opened. Install or configure a default browser."

        browser_label = "Chrome" if browser_name else "default browser"
        return f"Opened {url} in {browser_label}."


BROWSER_APP = BrowserApp()