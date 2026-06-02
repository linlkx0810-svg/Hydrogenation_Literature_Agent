"""
logger.py
Structured event logging to a JSONL file.
"""

import json
from pathlib import Path
from typing import Any

from .text_utils import timestamp


def log_event(log_path: Path, event: str, **fields: Any) -> None:
    """Append a structured event to a JSONL log file."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    entry = {"time": timestamp(), "event": event, **fields}
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
