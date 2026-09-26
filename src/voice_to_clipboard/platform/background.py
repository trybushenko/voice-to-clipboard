"""Explicit console-independent hotkey host; no transcript logging."""
import os
import subprocess
import sys
import time
from .paths import data_dir
from .processes import spawn_background
from .frozen import module_command


def start(arguments, endpoint):
    from ..core.host_control import request
    try:
        status = request(endpoint, 'status')
    except (OSError, EOFError, ValueError, RuntimeError):
        pass
    else:
        return status
    path = data_dir() / 'logs' / 'hotkeys.log'
    path.parent.mkdir(parents=True, exist_ok=True)
    # One diagnostic file per launch. Children use DEVNULL, so transcripts never
    # enter this log; history remains managed by the existing history settings.
    environment = dict(os.environ, DICTATE_BACKGROUND='1')
    with path.open('w', encoding='utf-8') as log:
        os.chmod(path, 0o600)
        process = spawn_background(
            module_command('voice_to_clipboard.ui.hotkeys', *arguments),
            no_console=True, env=environment, stdin=subprocess.DEVNULL,
            stdout=log, stderr=log)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f'Hotkey host exited ({process.returncode}); see {path}')
        try:
            return request(endpoint, 'status')
        except (OSError, EOFError, ValueError, RuntimeError):
            time.sleep(.1)
    process.terminate()
    process.wait(timeout=5)
    raise RuntimeError(f'Hotkey host did not become ready; see {path}')
