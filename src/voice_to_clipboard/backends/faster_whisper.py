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

