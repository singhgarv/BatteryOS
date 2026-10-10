import json
import os
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def default_log_path() -> Path:
    state_home = os.environ.get("XDG_STATE_HOME")
    if state_home:
        root = Path(state_home)
    elif platform.system() == "Windows":
        root = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "state"
    else:
        root = Path.home() / ".local" / "state"
    return root / "batteryos" / "events.jsonl"


class EventLogger:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path is not None else default_log_path()

    @staticmethod
    def make_event(event_type: str, data: dict[str, Any], timestamp: str | None = None) -> dict[str, Any]:
        if not event_type.strip():
            raise ValueError("event_type must not be empty")
        if timestamp is None:
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        return {
            "schema_version": 1,
            "timestamp": timestamp,
            "event_type": event_type,
            "data": data,
        }

    def write(self, event_type: str, data: dict[str, Any], timestamp: str | None = None) -> dict[str, Any]:
        event = self.make_event(event_type, data, timestamp)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as log_file:
            log_file.write(json.dumps(event, ensure_ascii=True, sort_keys=True) + "\n")
        return event

    def read(self, limit: int = 100) -> list[dict[str, Any]]:
        if limit < 1:
            raise ValueError("limit must be positive")
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        events = []
        for line in lines[-limit:]:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        return events