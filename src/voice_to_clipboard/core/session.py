import os
import socket
import threading
from ..platform.paths import cache_dir
from ..worker.transport import Server, connect

SOCK = str(cache_dir() / "dictate.sock")

def try_stop_running():
    if not os.path.exists(SOCK):
        return False
    try:
        with connect(SOCK, timeout=0.5) as s:
            s.sendall(b"stop")
        return True
    except socket.timeout:
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        if os.path.exists(SOCK):
            os.unlink(SOCK)                      # осиротілий сокет після падіння
        return False


def stop_listener(stop_event):
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = Server(SOCK)

    def serve():
        try:
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(2)
                if conn.recv(4) == b"stop":
                    stop_event.set()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    return srv

