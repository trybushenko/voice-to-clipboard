import os
import socket
import threading
from ..platform.paths import cache_dir
from ..platform.files import remove_endpoint
from pathlib import Path
from ..worker.transport import Server, connect

SOCK = os.environ.get("DICTATE_SESSION_ENDPOINT", str(cache_dir() / "dictate.sock"))
GLOBAL_LOCK = str(cache_dir() / "dictate.sock.lock")

def try_stop_running(path=None):
    path = path or SOCK
    if not os.path.exists(path):
        return False
    try:
        with connect(path, timeout=0.5) as s:
            s.sendall(b"stop")
        return True
    except socket.timeout:
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        if os.path.exists(path):
            remove_endpoint(Path(path))                      # осиротілий сокет після падіння
        return False


def stop_listener(stop_event):
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    srv = Server(SOCK)

    def serve():
        try:
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(2)
                message = b""
                while len(message) < 4:
                    part = conn.recv(4 - len(message))
                    if not part:
                        break
                    message += part
                if message == b"stop":
                    stop_event.set()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    return srv

