import unittest
import webbrowser
from unittest.mock import Mock, patch

from apps.browser import BrowserApp, normalize_url
from commands.registry import execute_command


class BrowserUrlTests(unittest.TestCase):
    def test_normalizes_host_and_preserves_https_url(self) -> None:
        self.assertEqual(normalize_url("example.com"), "https://example.com")
        self.assertEqual(
            normalize_url("https://example.com/path?q=1"),
            "https://example.com/path?q=1",
        )

    def test_rejects_unsupported_or_malformed_urls(self) -> None:
        self.assertIsNone(normalize_url("javascript:alert(1)"))
        self.assertIsNone(normalize_url("file:///etc/passwd"))
        self.assertIsNone(normalize_url("https://example.com:invalid"))
        self.assertIsNone(normalize_url("not a url"))


class BrowserAppTests(unittest.TestCase):
    def test_opens_normalized_url_in_default_browser(self) -> None:
        opener = Mock(return_value=True)
        app = BrowserApp(opener)

        result = app.open("example.com")

        self.assertEqual(result, "Opened https://example.com in default browser.")
        opener.assert_called_once_with("https://example.com", None)

    def test_opens_blank_tab_when_no_url_is_given(self) -> None:
        opener = Mock(return_value=True)
        app = BrowserApp(opener)

        app.open()

        opener.assert_called_once_with("about:blank", None)

    def test_reports_missing_browser_or_chrome(self) -> None:
        app = BrowserApp(Mock(return_value=False))
        self.assertIn("No browser could be opened", app.open("example.com"))

        unavailable = BrowserApp(Mock(side_effect=webbrowser.Error("not installed")))
        self.assertIn("Unable to open Chrome", unavailable.open(browser_name="chrome"))

    def test_invalid_url_is_not_sent_to_browser(self) -> None:
        opener = Mock(return_value=True)
        app = BrowserApp(opener)

        self.assertIn("Invalid URL", app.open("javascript:alert(1)"))
        opener.assert_not_called()

    def test_browse_command_uses_default_browser(self) -> None:
        with patch("commands.actions.BROWSER_APP.open", return_value="opened") as opener:
            self.assertEqual(execute_command("browse example.com/path"), "opened")

        opener.assert_called_once_with("example.com/path", browser_name=None)

    def test_browse_requires_a_url(self) -> None:
        self.assertEqual(execute_command("browse"), "Usage: browse <url>")


if __name__ == "__main__":
    unittest.main()