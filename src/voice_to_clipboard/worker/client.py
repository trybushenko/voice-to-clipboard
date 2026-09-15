import base64
import os
import subprocess
import sys
import time
from types import SimpleNamespace
import numpy as np
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
        while True:
            try:
                self.sock = connect(self.runtime / 'worker.sock')
                break
            except (FileNotFoundError, ConnectionRefusedError):
                if not launched:
                    subprocess.Popen([sys.executable, '-m', 'voice_to_clipboard.worker.service'],
                                     env={**os.environ, 'DICTATE_RUNTIME': str(self.runtime)},
                                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL, start_new_session=True,
                                     close_fds=True)
                    launched = True
                if time.monotonic() >= deadline:
                    raise TimeoutError('Не вдалося запустити фонову модель')
                time.sleep(.1)
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

