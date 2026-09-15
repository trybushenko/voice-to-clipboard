import json
import struct

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

