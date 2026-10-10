import json
from pathlib import Path
from typing import Any


def load_config(filename: str) -> dict[str, Any]:
    path = Path(__file__).with_name(filename)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Configuration must contain a JSON object: {filename}")
    return data