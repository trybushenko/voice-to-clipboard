import importlib
from types import SimpleNamespace

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

