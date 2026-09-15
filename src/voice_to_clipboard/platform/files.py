"""Bounded handling of Windows endpoint sharing violations."""
import sys
import time


def retry_file(operation, path, timeout=2.0):
    deadline = time.monotonic() + timeout
    delay = .025
    while True:
        try:
            return operation()
        except PermissionError as exc:
            if sys.platform != 'win32':
                raise
            if time.monotonic() >= deadline:
                raise PermissionError(
                    f'Cannot access local endpoint {path}. Close applications locking '
                    'this file and retry dictation.') from exc
            time.sleep(min(delay, max(0, deadline - time.monotonic())))
            delay = min(delay * 2, .2)


def remove_endpoint(path):
    retry_file(lambda: path.unlink(missing_ok=True), path)
