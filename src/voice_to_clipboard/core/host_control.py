"""Private control channel and explicit listener pause/resume lifecycle."""
import queue
import socket
import threading
import time
from ..worker.transport import Server, connect
from ..worker.protocol import receive, send

OPERATIONS = {'pause', 'resume', 'status', 'stop-recording', 'quit', 'check-paste'}


def request(path, operation, **details):
    with connect(path, timeout=10) as sock:
        send(sock, {'op': operation, **details})
        result = receive(sock)
    if 'error' in result:
        raise RuntimeError(result['error'])
    return result


class ControlServer:
    def __init__(self, path):
        self.requests = queue.Queue(maxsize=8)
        self.stopping = threading.Event()
        self.server = Server(path)
        self.server.settimeout(.2)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        while not self.stopping.is_set():
            try:
                conn, _ = self.server.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with conn:
                conn.settimeout(1)
                try:
                    payload = receive(conn)
                    operation = payload.get('op') if isinstance(payload, dict) else None
                    if not isinstance(operation, str) or operation not in OPERATIONS:
                        send(conn, {'error': 'Unknown hotkey operation'})
                        continue
                    reply = queue.Queue(maxsize=1)
                    cancelled = threading.Event()
                    self.requests.put_nowait((payload, reply, cancelled))
                    deadline = time.monotonic() + 8
                    while True:
                        try:
                            send(conn, reply.get(timeout=.1))
                            break
                        except queue.Empty:
                            if self.stopping.is_set() or time.monotonic() >= deadline:
                                cancelled.set()
                                send(conn, {"error": "Hotkey host stopped or request timed out"})
                                break
                            continue
                except (OSError, EOFError, ValueError, queue.Full):
                    continue

    def dispatch(self, handler):
        """Run listener mutations only on the owning main thread."""
        for _ in range(8):
            try:
                operation, reply, cancelled = self.requests.get_nowait()
            except queue.Empty:
                return
            if cancelled.is_set():
                continue
            try:
                result = handler(operation)
            except Exception as exc:
                result = {'error': str(exc)}
            reply.put_nowait(result)

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=2)
        self.server.close()


class ListenerController:
    def __init__(self, factory, enqueue):
        self.factory = factory
        self.enqueue = enqueue
        self.listener = None
        self.paused = True
        self.generation = 0

    def resume(self):
        if not self.paused:
            return
        if self.listener is not None and self.listener.is_alive():
            raise RuntimeError('Previous listener has not stopped; cannot resume yet')
        self.generation += 1
        generation = self.generation
        def emit(lang, paste=False):
            if not self.paused and generation == self.generation:
                self.enqueue((generation, lang, paste))
        callbacks = {'u': lambda: emit('uk'), 'e': lambda: emit('en'),
                     'l': lambda: emit('uk', True)}
        listener = self.factory(callbacks)
        try:
            listener.start()
        except Exception:
            listener.stop()
            if listener.ident is not None:
                listener.join(timeout=2)
            raise
        self.listener = listener
        self.paused = False

    def pause(self):
        self.paused = True
        self.generation += 1  # Discard any action queued before the pause.
        if self.listener is not None:
            self.listener.stop()
            if self.listener.ident is not None:
                self.listener.join(timeout=2)
            if self.listener.is_alive():
                raise RuntimeError('Hotkey listener is still stopping; retry pause before resume')

    def accepts(self, generation):
        return not self.paused and generation == self.generation
