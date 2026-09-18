"""User shortcut preference, stored separately from transcripts."""
import json
import os
import tempfile
from ..platform.paths import data_dir


def read_settings():
    path = data_dir() / 'settings.json'
    try:
        result = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(result, dict):
            raise ValueError('Expected an object')
        return result
    except FileNotFoundError:
        return {}
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(f'Invalid shortcut settings: {path}. Remove or repair this file.') from exc


def read_modifiers():
    return read_settings().get("hotkey_modifiers", "alt+shift")


def save_modifiers(value):
    save_settings({"hotkey_modifiers": value})


def save_settings(values):
    path = data_dir() / 'settings.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        settings = {}
    settings.update(values)
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(settings, stream, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
