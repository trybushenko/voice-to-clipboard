import sys


def resolve_device(device, cuda_count):
    """The Windows standalone distribution ships CPU dependencies only."""
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        if device == "cuda":
            raise ValueError("This Windows bundle supports CPU only. Select CPU or auto in Settings; use a source installation for CUDA.")
        if device == "auto":
            return "cpu"
    return ("cuda" if cuda_count() else "cpu") if device == "auto" else device


class FasterModel:
    def __init__(self, name, compute, device):
        import ctranslate2
        from faster_whisper import WhisperModel
        device = resolve_device(device, ctranslate2.get_cuda_device_count)
        if compute == 'auto':
            compute = 'float16' if device == 'cuda' else 'int8'
        self.model = WhisperModel(name, device=device, compute_type=compute)

    def transcribe(self, audio, **options):
        return self.model.transcribe(audio, **options)

    def unload(self):
        self.model.model.unload_model()

