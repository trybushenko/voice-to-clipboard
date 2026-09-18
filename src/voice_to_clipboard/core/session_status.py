"""Private, transcript-free lifecycle updates from a recording child."""
import json
import os
from pathlib import Path
import tempfile

STATES = {'starting', 'recording', 'transcribing', 'delivered', 'error'}


def publish(state, message=''):
    path = os.environ.get('DICTATE_STATUS_PATH')
    if not path or state not in STATES:
        return
    path = Path(path)
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump({'state': state, 'message': message}, stream)
        from ..platform.files import retry_file
        retry_file(lambda: os.replace(temporary, path), path)
    except OSError:
        pass  # UI telemetry must not interrupt clipboard delivery.
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
