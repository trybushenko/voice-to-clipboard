"""Persistent speech model worker; launch with python -m voice_to_clipboard.worker.service."""
import base64
import os
import socket
import numpy as np
from ..platform.desktop import SessionLock
from ..backends import factory
from .config import RUNTIME
from .transport import Server
from .protocol import receive, send

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


if __name__ == "__main__":
    serve()
