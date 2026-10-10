import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from apps.launcher import list_apps, open_app
from apps.notes import NotesStore, handle_notes
from commands.registry import execute_command


class NotesStoreTests(unittest.TestCase):
    def test_notes_persist_and_support_read_and_delete(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "notes.json"
            store = NotesStore(path)

            self.assertEqual(store.add_note("Pack charger"), 1)
            reopened_store = NotesStore(path)
            self.assertEqual(reopened_store.get_note(1), {"id": 1, "text": "Pack charger"})
            self.assertTrue(reopened_store.delete_note(1))
            self.assertEqual(reopened_store.list_notes(), [])

    def test_note_commands_report_empty_and_invalid_requests(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = NotesStore(Path(temporary_directory) / "notes.json")

            self.assertIn("No notes yet", handle_notes(store=store))
            self.assertIn("Usage: notes add", handle_notes("add", store))
            self.assertEqual(handle_notes("read x", store), "Usage: notes read <id>")


class AppLayerTests(unittest.TestCase):
    def test_open_notes_returns_the_notes_view(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            store = NotesStore(Path(temporary_directory) / "notes.json")
            self.assertIn("No notes yet", handle_notes(store=store))

        self.assertEqual(open_app("notepad"), execute_command("notes"))

    def test_app_directory_lists_available_and_deferred_apps(self) -> None:
        directory = list_apps()

        self.assertIn("settings", directory)
        self.assertIn("notes", directory)
        self.assertIn("browser", directory)
        self.assertIn("Default browser", directory)

    def test_open_browser_routes_url_to_default_browser(self) -> None:
        with patch("commands.actions.BROWSER_APP.open", return_value="opened") as opener:
            self.assertEqual(open_app("browser example.com"), "opened")

        opener.assert_called_once_with("example.com", browser_name=None)

    def test_open_chrome_uses_the_chrome_browser_name(self) -> None:
        with patch("commands.actions.BROWSER_APP.open", return_value="opened") as opener:
            self.assertEqual(open_app("chrome example.com"), "opened")

        opener.assert_called_once_with("example.com", browser_name="chrome")


if __name__ == "__main__":
    unittest.main()