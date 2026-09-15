import sys
import threading
import numpy as np

_out_lock = threading.Lock()

def emit(text, tty):
    """Друк рядка так, щоб не побити рядок метра."""
    with _out_lock:
        if tty:
            sys.stderr.write("\r\033[K")
        sys.stderr.write(text + "\n")
        sys.stderr.flush()


def meter(gate, elapsed, model_ready):
    lo, hi = -60.0, -5.0
    frac = float(np.clip((gate.last_db - lo) / (hi - lo), 0.0, 1.0))
    bar = "█" * int(frac * 22) + "░" * (22 - int(frac * 22))
    if gate.in_speech:
        state = "\033[32m● МОВЛЕННЯ\033[0m"
    elif gate.armed:
        state = f"\033[33m  пауза {gate.silence_run:4.1f}s\033[0m"
    else:
        state = "\033[2m  чекаю…   \033[0m"
    flags = ("V" if gate.vad_hit else "·") + ("M" if model_ready else "·")
    return (f"\r\033[K[{elapsed:5.1f}s] {gate.last_db:6.1f} dB "
            f"|{bar}| фон {gate.floor_db:6.1f} поріг {gate.threshold_db:6.1f} "
            f"{flags} {state}")

