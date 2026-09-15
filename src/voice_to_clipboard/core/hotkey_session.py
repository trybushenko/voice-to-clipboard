"""One owned session; the starting shortcut determines language and delivery."""
import json
import os
import sys
from ..platform.processes import spawn_background
from .session import try_stop_running


class SessionLauncher:
    def __init__(self, args):
        self.args = args
        self.children = []
        self.pending_stop = False

    def tick(self):
        self.children[:] = [p for p in self.children if p.poll() is None]
        if not self.children:
            self.pending_stop = False
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
        environment.pop('DICTATE_PASTE_TARGET', None)
        if paste:
            command.append('--paste')
            if sys.platform == 'win32':
                from ..platform.focus import capture_windows_target
                environment['DICTATE_PASTE_TARGET'] = json.dumps(capture_windows_target())
        if not self.args.no_overlay:
            command.append('--overlay')
        self.children.append(spawn_background(command, env=environment))
