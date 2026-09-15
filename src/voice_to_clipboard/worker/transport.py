"""Unix sockets on Linux/macOS; authenticated loopback TCP on Windows."""
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
from ..platform.files import retry_file, remove_endpoint


def connect(path, timeout=900):
    tcp = sys.platform == 'win32'
    sock = socket.socket(socket.AF_INET if tcp else socket.AF_UNIX)
    sock.settimeout(timeout)
    try:
        if tcp:
            info = json.loads(Path(path).read_text())
            sock.connect(('127.0.0.1', info['port']))
            sock.sendall(info['token'].encode('ascii'))
            acknowledgement = b''
            while len(acknowledgement) < 2:
                part = sock.recv(2 - len(acknowledgement))
                if not part:
                    break
                acknowledgement += part
            if acknowledgement != b'OK':
                raise ConnectionRefusedError('Local service authentication failed')
        else:
            sock.connect(str(path))
        return sock
    except Exception:
        sock.close()
        raise


class Server:
    def __init__(self, path):
        self.path = Path(path)
        self.tcp = sys.platform == 'win32'
        self.socket = socket.socket(socket.AF_INET if self.tcp else socket.AF_UNIX)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self.tcp:
                self.socket.bind(('127.0.0.1', 0))
                self.socket.listen(4)
                self.token = secrets.token_hex(32).encode('ascii')
                fd, tmp = retry_file(lambda: tempfile.mkstemp(dir=self.path.parent), self.path)
                try:
                    with os.fdopen(fd, 'w') as f:
                        json.dump({'port': self.socket.getsockname()[1], 'token': self.token.decode()}, f)
                    retry_file(lambda: os.replace(tmp, self.path), self.path)
                finally:
                    remove_endpoint(Path(tmp))
            else:
                remove_endpoint(self.path)
                self.socket.bind(str(path))
                os.chmod(path, 0o600)
                self.socket.listen(4)
        except Exception:
            self.socket.close()
            raise

    def settimeout(self, timeout):
        self.socket.settimeout(timeout)

    def accept(self):
        while True:
            conn, address = self.socket.accept()
            if self.tcp:
                conn.settimeout(2)
                try:
                    token = b''
                    while len(token) < 64:
                        part = conn.recv(64 - len(token))
                        if not part:
                            break
                        token += part
                    if not secrets.compare_digest(token, self.token):
                        conn.close()
                        continue
                    conn.sendall(b'OK')
                except OSError:
                    conn.close()
                    continue
            return conn, address

    def close(self):
        self.socket.close()
        remove_endpoint(self.path)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
