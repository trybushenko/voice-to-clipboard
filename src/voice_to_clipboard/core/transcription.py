import os
import queue
import threading
import time
from .speech_gate import SAMPLE_RATE
from ..ui.terminal import emit

INITIAL_PROMPT = os.environ.get(
    "DICTATE_PROMPT",
    "Технічний контекст: PyTorch, TFLite, ONNX, FAISS, quantization, encoder, "
    "inference, embedding, Docker, FastAPI, DVC, Bitbucket, OpenCV, edge AI, "
    "computer vision, pipeline, benchmark, latency, throughput, checkpoint.",
)

class Transcriber(threading.Thread):
    """Один потік, одна модель: faster-whisper не для паралельних викликів."""

    def __init__(self, holder, ready, args, tty):
        super().__init__(daemon=True)
        self.q = queue.Queue()
        self.holder = holder
        self.ready = ready
        self.args = args
        self.tty = tty
        self.parts = []
        self.errors = []

    def submit(self, audio):
        self.q.put(audio)

    def close(self):
        self.q.put(None)

    def _transcribe(self, audio):
        segments, _ = self.holder["model"].transcribe(
            audio,
            language=self.args.lang,
            beam_size=self.args.beam,
            vad_filter=True,                    # виріже паузи перед декодером
            vad_parameters={"min_silence_duration_ms": 500},
            condition_on_previous_text=False,   # інакше зациклюється на повторах
            initial_prompt=(INITIAL_PROMPT if self.args.lang == "uk" else
                            "Technical vocabulary: Python, FastAPI, Docker, API, GitHub, latency, inference."),
            temperature=0.0,
        )
        return " ".join(s.text.strip() for s in segments).strip()

    def run(self):
        while True:
            audio = self.q.get()
            if audio is None:
                return
            self.ready.wait()
            if "model" not in self.holder:
                return
            try:
                t = time.monotonic()
                text = self._transcribe(audio)
            except Exception as exc:
                emit(f"[retry] транскрипція: {exc}", self.tty)
                try:
                    text = self._transcribe(audio)
                except Exception as retry_exc:
                    self.errors.append(str(retry_exc))
                    emit(f"[error] фрагмент не розпізнано: {retry_exc}", self.tty)
                    continue
            if text:
                self.parts.append(text)
                emit(f"  › {text}"
                     + (f"   \033[2m[{len(audio)/SAMPLE_RATE:.1f}s → "
                        f"{time.monotonic()-t:.2f}s]\033[0m" if self.tty else ""),
                     self.tty)


def load_model(holder, ready, name, compute, tty, one_shot=False, backend="auto", device="auto"):
    try:
        from ..worker.client import RemoteModel
        from ..backends import factory
        m = (factory(name, compute, backend, device) if one_shot else
             RemoteModel(name, compute, backend=backend, device=device))
        holder["model"] = m
    except Exception as exc:
        holder["error"] = exc
        emit(f"[error] модель: {exc}", tty)
    finally:
        ready.set()

