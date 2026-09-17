"""User shortcut preference, stored separately from transcripts."""
import json
import os
import tempfile
from ..platform.paths import data_dir


def read_modifiers():
    path = data_dir() / 'settings.json'
    try:
        return json.loads(path.read_text(encoding='utf-8')).get('hotkey_modifiers', 'alt+shift')
    except FileNotFoundError:
        return 'alt+shift'
    except (ValueError, AttributeError) as exc:
        raise RuntimeError(f'Invalid shortcut settings: {path}. Remove or repair this file.') from exc


def save_modifiers(value):
    path = data_dir() / 'settings.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        settings = json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        settings = {}
    settings['hotkey_modifiers'] = value
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(settings, stream, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
