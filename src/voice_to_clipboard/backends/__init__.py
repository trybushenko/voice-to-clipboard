"""Speech backend selection and common factory."""
import platform
import sys
import numpy as np
from .mlx import MLXModel
from .faster_whisper import FasterModel

def resolve_backend(backend='auto', device='auto'):
    if backend != 'auto':
        return backend
    if sys.platform == 'darwin' and platform.machine().lower() in ('arm64', 'aarch64') and device != 'cpu':
        return 'mlx'
    return 'faster-whisper'


def factory(name, compute='auto', backend='auto', device='auto'):
    backend = resolve_backend(backend, device)
    if backend == 'mlx':
        if sys.platform != 'darwin' or platform.machine().lower() not in ('arm64', 'aarch64'):
            raise RuntimeError('MLX requires native arm64 Python on an Apple Silicon Mac')
        if device not in ('auto', 'metal'):
            raise ValueError('MLX uses Metal; choose --backend faster-whisper for CPU')
        model = MLXModel(name)
    else:
        if device == 'metal':
            raise ValueError('Metal requires the MLX backend')
        model = FasterModel(name, compute, device)
    list(model.transcribe(np.zeros(16000, dtype=np.float32), language='en', beam_size=1)[0])
    return model

