"""Signal-aware recording and bounded hotkey shutdown helpers."""
from contextlib import contextmanager
import signal


@contextmanager
def stop_on_interrupt(stop_event):
    """Keep Python waits interruptible while draining the final transcription."""
    def stop(signum, frame):
        stop_event.set()
    previous = signal.signal(signal.SIGINT, stop)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
