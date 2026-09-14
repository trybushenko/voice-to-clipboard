"""Private local Whisper worker. One connection owns the model per session."""
import base64
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
from platform_support import SessionLock, cache_dir
from local_ipc import Server, connect
from speech_backends import factory

RUNTIME = Path(os.environ.get('DICTATE_RUNTIME', str(cache_dir() / 'dictate-worker')))
MAX_PACKET = 128 * 1024 * 1024


def receive(sock):
    def exact(size):
        data = bytearray()
        while len(data) < size:
            part = sock.recv(size - len(data))
            if not part:
                raise EOFError('Worker connection closed')
            data.extend(part)
        return bytes(data)
    size = struct.unpack('!I', exact(4))[0]
    if size > MAX_PACKET:
        raise ValueError('Worker packet too large')
    return json.loads(exact(size))


def send(sock, value):
    data = json.dumps(value, ensure_ascii=False).encode()
    if len(data) > MAX_PACKET:
        raise ValueError('Worker packet too large')
    sock.sendall(struct.pack('!I', len(data)) + data)


def serve(runtime=RUNTIME, idle=300, make_model=factory):
    runtime.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(runtime, 0o700)
    try:
        lock = SessionLock(runtime / 'worker.lock')
    except BlockingIOError:
        return
    with lock:
        path = runtime / 'worker.sock'
        path.unlink(missing_ok=True)
        model, config = None, None
        with Server(path) as server:
            server.settimeout(idle)
            try:
                while True:
                    try:
                        conn, _ = server.accept()
                    except socket.timeout:
                        return  # Process exit reliably releases CUDA allocations.
                    with conn:
                        conn.settimeout(900)
                        try:
                            while True:
                                request = receive(conn)
                                op = request.get('op')
                                if op == 'status':
                                    send(conn, {'loaded': model is not None, 'config': config})
                                    break
                                if op == 'shutdown':
                                    send(conn, {'ok': True})
                                    return
                                if op == 'load':
                                    desired = [request['name'], request['compute'], request.get('backend', 'auto'), request.get('device', 'auto')]
                                    if config != desired:
                                        if model is not None:
                                            # Do not briefly allocate two large GPU models.
                                            model.unload()
                                            model = None
                                            config = None
                                        model = make_model(*desired)
                                        config = desired
                                    send(conn, {'ok': True})
                                elif op == 'transcribe':
                                    if model is None:
                                        raise RuntimeError('Model is not loaded')
                                    audio = np.frombuffer(base64.b64decode(request['audio'], validate=True), dtype='<f4')
                                    segments, _ = model.transcribe(audio, **request['options'])
                                    send(conn, {'segments': [s.text for s in segments]})
                                else:
                                    raise ValueError('Unknown worker operation')
                        except (EOFError, ConnectionError, socket.timeout):
                            pass
                        except Exception as exc:
                            try:
                                send(conn, {'error': str(exc)})
                            except OSError:
                                pass
            finally:
                path.unlink(missing_ok=True)


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
                    subprocess.Popen([sys.executable, str(Path(__file__).resolve())],
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


if __name__ == '__main__':
    serve()
