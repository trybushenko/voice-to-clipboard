"""Measure isolated cold/warm readiness using cached weights; no microphone."""
import os
from pathlib import Path
import site
import tempfile
import time


def main():
    # Optional pip-installed CUDA libraries, without hardcoding Python/user paths.
    libraries = [str(Path(base) / 'nvidia' / name / 'lib')
                 for base in site.getsitepackages()
                 for name in ('cublas', 'cuda_nvrtc', 'cudnn')
                 if (Path(base) / 'nvidia' / name / 'lib').is_dir()]
    if libraries:
        os.environ['LD_LIBRARY_PATH'] = os.pathsep.join(libraries + [os.environ.get('LD_LIBRARY_PATH', '')])
    os.environ['HF_HUB_OFFLINE'] = '1'
    with tempfile.TemporaryDirectory(prefix='dictate-bench-') as runtime:
        os.environ['DICTATE_RUNTIME'] = runtime
        from voice_to_clipboard.worker.client import RemoteModel, control
        import numpy as np
        try:
            for label in ('cold', 'warm'):
                start = time.monotonic()
                model = RemoteModel('large-v3-turbo', 'auto')
                try:
                    print(f'{label}: model ready in {time.monotonic() - start:.3f}s', flush=True)
                    segments, _ = model.transcribe(np.zeros(16000, dtype=np.float32), language='uk', beam_size=1, vad_filter=True)
                    print(f'{label}: silence decoded, {len(segments)} segments', flush=True)
                finally:
                    model.close()
            print(control('status'), flush=True)
        finally:
            print(control('shutdown'), flush=True)
            # Wait for the worker to remove its socket before deleting runtime.
            deadline = time.monotonic() + 5
            while (Path(runtime) / 'worker.sock').exists() and time.monotonic() < deadline:
                time.sleep(.05)


if __name__ == '__main__':
    main()
