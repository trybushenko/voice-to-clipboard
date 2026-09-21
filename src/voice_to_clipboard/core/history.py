import json
import os
from pathlib import Path
import tempfile
import time
from ..platform.paths import data_dir

HISTORY = Path(os.environ.get("DICTATE_HISTORY", str(data_dir() / "history.json")))

def read_history():
    try:
        entries = json.loads(HISTORY.read_text(encoding="utf-8"))
        if not isinstance(entries, list) or any(
            not isinstance(e, dict) or not isinstance(e.get("text"), str)
            for e in entries
        ):
            raise ValueError("Invalid history format")
        return entries
    except FileNotFoundError:
        return []


def save_history(text, complete=True):
    entries = read_history()
    entries.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "text": text, "complete": complete})
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".dictate-history-", dir=HISTORY.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(entries[-50:], f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, HISTORY)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def latest_text():
    return next((e["text"] for e in reversed(read_history())
                 if e.get("complete", True) and e.get("kind") != "prompt"), "")

