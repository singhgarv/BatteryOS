import json
import os
import platform
from pathlib import Path


class NotesStore:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else self._default_path()

    @staticmethod
    def _default_path() -> Path:
        data_home = os.environ.get("XDG_DATA_HOME")
        if data_home:
            root = Path(data_home)
        elif platform.system() == "Windows":
            root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        else:
            root = Path.home() / ".local" / "share"
        return root / "battery-os" / "notes.json"

    def list_notes(self) -> list[dict[str, int | str]]:
        try:
            content = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return []

        try:
            notes = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("Notes data is not valid JSON.") from error

        if not isinstance(notes, list) or any(
            not isinstance(note, dict)
            or not isinstance(note.get("id"), int)
            or not isinstance(note.get("text"), str)
            for note in notes
        ):
            raise ValueError("Notes data has an invalid format.")
        return notes

    def _save(self, notes: list[dict[str, int | str]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        temporary_path.write_text(
            json.dumps(notes, ensure_ascii=True, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_path.replace(self.path)

    def add_note(self, text: str) -> int:
        notes = self.list_notes()
        note_id = max((int(note["id"]) for note in notes), default=0) + 1
        notes.append({"id": note_id, "text": text})
        self._save(notes)
        return note_id

    def get_note(self, note_id: int) -> dict[str, int | str] | None:
        return next((note for note in self.list_notes() if note["id"] == note_id), None)

    def delete_note(self, note_id: int) -> bool:
        notes = self.list_notes()
        remaining = [note for note in notes if note["id"] != note_id]
        if len(remaining) == len(notes):
            return False
        self._save(remaining)
        return True


NOTES_STORE = NotesStore()


def handle_notes(arguments: str = "", store: NotesStore | None = None) -> str:
    notes_store = store or NOTES_STORE
    action, _, value = arguments.strip().partition(" ")
    action = action.casefold()
    value = value.strip()

    try:
        if not action or action == "list":
            notes = notes_store.list_notes()
            if not notes:
                return "No notes yet. Add one with: notes add <text>"
            return "Notes:\n" + "\n".join(
                f"{note['id']}. {note['text']}" for note in notes
            )

        if action == "add":
            if not value:
                return "Usage: notes add <text>"
            return f"Saved note #{notes_store.add_note(value)}."

        if action in {"read", "delete"}:
            try:
                note_id = int(value)
            except ValueError:
                return f"Usage: notes {action} <id>"
            if action == "read":
                note = notes_store.get_note(note_id)
                if note is None:
                    return f"Note #{note_id} not found."
                return f"Note #{note_id}: {note['text']}"
            if notes_store.delete_note(note_id):
                return f"Deleted note #{note_id}."
            return f"Note #{note_id} not found."
    except (OSError, ValueError) as error:
        return f"Notes unavailable: {error}"

    return "Usage: notes [list | add <text> | read <id> | delete <id>]"