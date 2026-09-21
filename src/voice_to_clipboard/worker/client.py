import base64
import os
import subprocess
import sys
import time
from types import SimpleNamespace
import numpy as np
from ..platform.processes import spawn_background
from .config import RUNTIME
from .transport import connect
from .protocol import receive, send

class RemoteModel:
    def __init__(self, name, compute, runtime=RUNTIME, backend="auto", device="auto"):
        self.runtime = runtime
        self.name, self.compute = name, compute
        self.backend, self.device = backend, device
        self.sock = None
        self.connect()

    def connect(self):
        self.close()
        self.runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
        launched = False
        deadline = time.monotonic() + 15
        delay = .025
        path = self.runtime / 'worker.sock'
        while True:
            try:
                self.sock = connect(path, timeout=max(.01, min(2, deadline - time.monotonic())))
                self.sock.settimeout(900)
                break
            except (FileNotFoundError, ConnectionRefusedError, PermissionError, TimeoutError) as exc:
                if not launched and not isinstance(exc, PermissionError):
                    spawn_background([sys.executable, '-m', 'voice_to_clipboard.worker.service'],
                                     env={**os.environ, 'DICTATE_RUNTIME': str(self.runtime)},
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, no_console=True)
                    launched = True
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'Could not connect to the model: {path}. '
                                       'Check file access and retry dictation.') from exc
                time.sleep(min(delay, max(0, deadline - time.monotonic())))
                delay = min(delay * 2, .25)
        try:
            self.request({'op': 'load', 'name': self.name, 'compute': self.compute, 'backend': self.backend, 'device': self.device})
        except Exception:
            self.close()
            raise

    def request(self, payload):
        send(self.sock, payload)
        result = receive(self.sock)
        if 'error' in result:
            raise RuntimeError(result['error'])
        return result

    def transcribe(self, audio, **options):
        if self.sock is None:
            self.connect()
        try:
            result = self.request({'op': 'transcribe', 'options': options,
                                   'audio': base64.b64encode(np.asarray(audio, dtype='<f4').tobytes()).decode()})
        except Exception:
            self.close()  # Existing Transcriber retry reconnects to the worker.
            raise
        return [SimpleNamespace(text=t) for t in result['segments']], None

    def close(self):
        if self.sock is not None:
            self.sock.close()
            self.sock = None


def control(operation):
    try:
        sock = connect(RUNTIME / 'worker.sock', timeout=2)
    except (FileNotFoundError, ConnectionRefusedError):
        return {'loaded': False, 'running': False}
    with sock:
        send(sock, {'op': operation})
        return receive(sock)

