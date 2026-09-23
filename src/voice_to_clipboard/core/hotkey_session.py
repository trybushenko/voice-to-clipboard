"""One owned session; the starting shortcut determines language and delivery."""
import os
import sys
import secrets
import subprocess
import json
import tempfile
import time
from pathlib import Path
from ..platform.processes import spawn_background
from .session import try_stop_running


class SessionLauncher:
    def __init__(self, args):
        self.args = args
        self.children = []
        self.pending_stop = False
        self.paste_guard = None
        self.paste_token = None
        self.state, self.message = 'idle', 'Ready'
        self.completed_at = 0
        self.status_path = None
        self.worker = None
        self.runtime = None
        self.runtime_owner = None
        self.log_threads = []
        if getattr(args, 'desktop', False):
            from ..platform.paths import cache_dir
            folder = cache_dir() / 'dictate-desktop'
            folder.mkdir(parents=True, exist_ok=True)
            self.runtime_owner = tempfile.TemporaryDirectory(prefix='host-', dir=folder)
            self.runtime = Path(self.runtime_owner.name)

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

    def shutdown(self):
        self.close()
        for child in self.children:
            self._terminate(child)
        self.children.clear()
        if self.worker is not None:
            self._terminate(self.worker)
            self.worker = None
        for thread in self.log_threads:
            thread.join(timeout=.5)
        if self.runtime_owner is not None:
            from ..platform.files import retry_file
            retry_file(self.runtime_owner.cleanup, self.runtime)
            self.runtime_owner = None

    @staticmethod
    def _terminate(process):
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def _ensure_worker(self):
        if self.worker is None or self.worker.poll() is not None:
            self.worker = spawn_background(
                [sys.executable, '-m', 'voice_to_clipboard.worker.service'],
                no_console=True, env={**os.environ, 'DICTATE_RUNTIME': str(self.runtime), 'DICTATE_TECHNICAL_ONLY': '1'},
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            from .app_logging import collect_process
            self.log_threads.append(collect_process(self.worker, 'worker'))
            deadline = time.monotonic() + 8
            while not (self.runtime / 'worker.sock').exists():
                if self.worker.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Model worker could not start. Run System check.')
                time.sleep(.05)

    def stop_running(self):
        return try_stop_running(str(self.runtime / "dictate.sock")) if self.runtime is not None else try_stop_running()

    def tick(self):
        if self.status_path is not None:
            try:
                status = json.loads(self.status_path.read_text(encoding='utf-8'))
                from .session_status import STATES
                if status.get('state') in STATES:
                    self.state = status['state']
                    self.message = str(status.get('message', ''))[:300]
            except (OSError, ValueError, AttributeError):
                pass
        for process in self.children:
            code = process.poll()
            if code not in (None, 0):
                if self.state != 'error':
                    self.state, self.message = 'error', f'Dictation exited ({code}). Run System check and inspect the log.'
                print(self.message, flush=True)
        was_active = bool(self.children)
        self.children[:] = [p for p in self.children if p.poll() is None]
        if not self.children:
            if was_active:
                if self.state not in ('delivered', 'error'):
                    self.state, self.message = 'delivered', 'Session finished'
                self.completed_at = time.monotonic()
                if self.status_path is not None:
                    self.status_path.unlink(missing_ok=True)
                    self.status_path = None
            elif self.state == 'delivered' and time.monotonic() - self.completed_at > 5:
                self.state, self.message = 'idle', 'Ready'
            self.pending_stop = False
            self.close()
        elif self.pending_stop:
            if self.stop_running():
                self.pending_stop = False

    def launch(self, lang, paste=False, model=None):
        self.tick()
        if self.children:
            # Never change the first invocation's language or --paste action.
            self.pending_stop = True
            self.tick()
            return
        if self.runtime is None and try_stop_running():
            return
        command = [sys.executable, '-m', 'voice_to_clipboard', '--lang', lang,
                   '--silence', '0', '--inference-device', self.args.inference_device]
        chosen_model = model or self.args.model or 'large-v3-turbo'
        from .model_compatibility import validate as validate_model
        try:
            validate_model(lang, chosen_model)
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        command += ['--model', chosen_model]
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
        if self.runtime is not None:
            self._ensure_worker()
            self.status_path = self.runtime / 'session.json'
            self.status_path.unlink(missing_ok=True)
            environment['DICTATE_RUNTIME'] = str(self.runtime)
            environment['DICTATE_SESSION_ENDPOINT'] = str(self.runtime / 'dictate.sock')
            environment['DICTATE_STATUS_PATH'] = str(self.status_path)
            environment['DICTATE_TECHNICAL_ONLY'] = '1'
        if not self.args.no_overlay:
            command.append('--overlay')
        try:
            options = {}
            if os.environ.get('DICTATE_BACKGROUND') == '1':
                options = dict(no_console=True, stdin=subprocess.DEVNULL,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if self.runtime is not None:
                options['stderr'] = subprocess.PIPE
            self.children.append(spawn_background(command, env=environment, **options))
            if self.runtime is not None:
                from .app_logging import collect_process
                self.log_threads.append(collect_process(self.children[-1], 'dictation'))
            self.state, self.message = 'starting', 'Starting microphone'
        except Exception:
            self.close()
            raise
