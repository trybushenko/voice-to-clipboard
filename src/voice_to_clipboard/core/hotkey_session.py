"""One owned session; the starting shortcut determines language and delivery."""
import os
import sys
import secrets
import subprocess
from ..platform.processes import spawn_background
from .session import try_stop_running


class SessionLauncher:
    def __init__(self, args):
        self.args = args
        self.children = []
        self.pending_stop = False
        self.paste_guard = None
        self.paste_token = None

    def close(self):
        if self.paste_guard is not None:
            self.paste_guard.close()
        self.paste_guard = None
        self.paste_token = None

    def check_paste(self, token):
        if not isinstance(token, str) or not self.paste_token or not secrets.compare_digest(token, self.paste_token):
            raise RuntimeError("Paste session expired; paste manually")
        self.paste_guard.check()
        return {"ok": True}

    def tick(self):
        for process in self.children:
            code = process.poll()
            if code not in (None, 0):
                print(f'Dictation exited with code {code}; retry in foreground for diagnostics.', flush=True)
        self.children[:] = [p for p in self.children if p.poll() is None]
        if not self.children:
            self.pending_stop = False
            self.close()
        elif self.pending_stop:
            if try_stop_running():
                self.pending_stop = False

    def launch(self, lang, paste=False):
        self.tick()
        if self.children:
            # Never change the first invocation's language or --paste action.
            self.pending_stop = True
            self.tick()
            return
        if try_stop_running():
            return
        command = [sys.executable, '-m', 'voice_to_clipboard', '--lang', lang,
                   '--silence', '0', '--inference-device', self.args.inference_device]
        if self.args.model:
            command += ['--model', self.args.model]
        if lang == 'en':
            command += ['--beam', '5']
        environment = dict(os.environ)
        for name in ('DICTATE_PASTE_TARGET', 'DICTATE_PASTE_TOKEN', 'DICTATE_CONTROL_PATH'):
            environment.pop(name, None)
        if paste:
            command.append('--paste')
            from ..platform.focus import make_guard
            from ..platform.paths import cache_dir
            self.paste_guard = make_guard(local=True)
            self.paste_token = secrets.token_hex(32)
            environment['DICTATE_PASTE_TOKEN'] = self.paste_token
            environment['DICTATE_CONTROL_PATH'] = str(cache_dir() / 'dictate-hotkey-control.sock')
        if not self.args.no_overlay:
            command.append('--overlay')
        try:
            options = {}
            if os.environ.get('DICTATE_BACKGROUND') == '1':
                options = dict(no_console=True, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.children.append(spawn_background(command, env=environment, **options))
        except Exception:
            self.close()
            raise
