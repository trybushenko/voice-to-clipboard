import threading
import time
import numpy as np
from .speech_gate import SAMPLE_RATE, BLOCK

class Recorder:
    def __init__(self, gate, device=None):
        import sounddevice as sd
        self.gate = gate
        self.frames = []
        self.n = 0
        self.lock = threading.Lock()
        self.stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1, dtype="float32",
            blocksize=BLOCK, device=device, callback=self._cb,
        )
        self.stream.start()
        self.t0 = time.monotonic()

    def _cb(self, indata, frames, tinfo, status):
        block = indata[:, 0].copy()
        with self.lock:
            self.frames.append(block)
            self.n += len(block)
            self.gate.push(block)

    def elapsed(self):
        return time.monotonic() - self.t0

    def slice_from(self, start):
        """Аудіо від семпла start до поточного моменту."""
        with self.lock:
            if not self.frames:
                return np.zeros(0, dtype=np.float32), 0
            total = self.n
            # Copy only the unprocessed tail, not the entire recording.
            selected = []
            remaining = total - start
            for block in reversed(self.frames):
                if remaining <= 0:
                    break
                selected.append(block[-remaining:] if remaining < len(block) else block)
                remaining -= len(block)
            return (np.concatenate(selected[::-1]) if selected
                    else np.zeros(0, dtype=np.float32)), total

    def finish(self):
        self.stream.stop()
        self.stream.close()
        with self.lock:
            return (np.concatenate(self.frames) if self.frames
                    else np.zeros(0, dtype=np.float32))

