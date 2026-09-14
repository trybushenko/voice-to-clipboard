"""Whisper adapters: MLX/Metal on Apple Silicon, CTranslate2 elsewhere."""
import importlib
import platform
import sys
from types import SimpleNamespace
import numpy as np


def resolve_backend(backend='auto', device='auto'):
    if backend != 'auto':
        return backend
    if sys.platform == 'darwin' and platform.machine().lower() in ('arm64', 'aarch64') and device != 'cpu':
        return 'mlx'
    return 'faster-whisper'


class MLXModel:
    def __init__(self, name):
        import mlx_whisper
        self.engine = mlx_whisper
        self.name = ('mlx-community/whisper-large-v3-turbo' if name == 'large-v3-turbo'
                     else name if '/' in name else 'mlx-community/whisper-' + name + '-mlx')

    def transcribe(self, audio, **options):
        options.pop('vad_filter', None)
        options.pop('vad_parameters', None)
        # MLX Whisper currently implements greedy decoding, not beam search.
        options.pop('beam_size', None)
        options.setdefault('temperature', 0.0)
        result = self.engine.transcribe(audio, path_or_hf_repo=self.name, verbose=None, **options)
        return [SimpleNamespace(text=s['text']) for s in result['segments']], None

    def unload(self):
        module = importlib.import_module('mlx_whisper.transcribe')
        module.ModelHolder.model = None
        module.ModelHolder.model_path = None
        import mlx.core as mx
        mx.clear_cache()


class FasterModel:
    def __init__(self, name, compute, device):
        import ctranslate2
        from faster_whisper import WhisperModel
        if device == 'auto':
            device = 'cuda' if ctranslate2.get_cuda_device_count() else 'cpu'
        if compute == 'auto':
            compute = 'float16' if device == 'cuda' else 'int8'
        self.model = WhisperModel(name, device=device, compute_type=compute)

    def transcribe(self, audio, **options):
        return self.model.transcribe(audio, **options)

    def unload(self):
        self.model.model.unload_model()


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
