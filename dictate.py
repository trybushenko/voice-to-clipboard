#!/usr/bin/env python3
"""
Локальне диктування з фоновою моделлю. Виклик -> начитав -> текст у буфері -> вихід.

У терміналі показує рівень мікрофона і транскрибує потоково: сегменти
нарізаються по твоїх паузах і розпізнаються у фоні, поки ти ще говориш.
Тому в кінці чекати майже нічого не треба.

Модель вантажиться паралельно із записом і зберігається між запусками.
GPU звільняється після 5 хвилин простою; --one-shot вимикає кешування.

Зупинка (перше, що настане):
  - тишa довше --silence секунд (після того, як щось було сказано)
  - повторний запуск того самого скрипта (той самий хоткей вдруге)
  - Ctrl+C
  - --max секунд
"""

import argparse
import atexit
import json
from pathlib import Path
import tempfile
import os
import queue
import socket
import subprocess
import sys
import threading
import time
from collections import deque

import numpy as np
from platform_support import SessionLock, cache_dir, data_dir, notify, to_clipboard, do_paste
from local_ipc import Server, connect

SAMPLE_RATE = 16000
BLOCK = 1024                 # ~64 мс
WEBRTC_FRAME = 480           # 30 мс — webrtcvad приймає тільки 10/20/30 мс
VAD_WINDOW = 16              # кадрів (~480 мс) для мажоритарного рішення
VAD_RATIO = 0.35             # частка кадрів-мовлення у вікні
VAD_MIN_OVER_FLOOR = 3.0     # VAD сам-один не тримає лінію біля рівня шуму
FLOOR_WINDOW = 5             # блоків (~320 мс) для оцінки шумового фону
PEAK_HEADROOM_DB = 6.0       # поріг мінімум на стільки нижче робочого рівня
ABS_MIN_DB = -58.0           # нижче цього не опускаємось (шум АЦП)
PEAK_DECAY_DB = 0.15         # спад піку за блок (~2.3 dB/с)
STUCK_WARN_S = 45.0          # попередити, якщо "мовлення" не вщухає
SOCK = str(cache_dir() / "dictate.sock")
HISTORY = Path(os.environ.get("DICTATE_HISTORY", str(data_dir() / "history.json")))

INITIAL_PROMPT = os.environ.get(
    "DICTATE_PROMPT",
    "Технічний контекст: PyTorch, TFLite, ONNX, FAISS, quantization, encoder, "
    "inference, embedding, Docker, FastAPI, DVC, Bitbucket, OpenCV, edge AI, "
    "computer vision, pipeline, benchmark, latency, throughput, checkpoint.",
)

_out_lock = threading.Lock()


def dbfs(x):
    return 20.0 * np.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-9)


def emit(text, tty):
    """Друк рядка так, щоб не побити рядок метра."""
    with _out_lock:
        if tty:
            sys.stderr.write("\r\033[K")
        sys.stderr.write(text + "\n")
        sys.stderr.flush()


# --------------------------------------------------------------------------
# Другий запуск = стоп для першого
# --------------------------------------------------------------------------

def try_stop_running():
    if not os.path.exists(SOCK):
        return False
    try:
        with connect(SOCK, timeout=0.5) as s:
            s.sendall(b"stop")
        return True
    except socket.timeout:
        return True
    except (ConnectionRefusedError, FileNotFoundError):
        if os.path.exists(SOCK):
            os.unlink(SOCK)                      # осиротілий сокет після падіння
        return False


def stop_listener(stop_event):
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    if os.path.exists(SOCK):
        os.unlink(SOCK)
    srv = Server(SOCK)

    def serve():
        try:
            conn, _ = srv.accept()
            with conn:
                conn.settimeout(2)
                if conn.recv(4) == b"stop":
                    stop_event.set()
        except OSError:
            pass

    threading.Thread(target=serve, daemon=True).start()
    return srv


# --------------------------------------------------------------------------
# Детектор мовлення
# --------------------------------------------------------------------------

class SpeechGate:
    """Стан "мовлення / тиша" і довжина поточної паузи.

    Два детектори по АБО, але WebRTC VAD не має права сам-один тримати лінію,
    якщо рівень сигналу біля шумового фону — інакше кулер і клавіатура не
    дають лічильнику паузи набратись і автостоп не спрацьовує ніколи.
    """

    def __init__(self, mode="auto", margin_min=6.0, margin_max=12.0,
                 hysteresis=4.0, aggressiveness=2):
        self.vad = None
        if mode in ("auto", "webrtc"):
            try:
                import webrtcvad
                self.vad = webrtcvad.Vad(aggressiveness)
            except ImportError:
                if mode == "webrtc":
                    sys.exit("webrtcvad не встановлений: "
                             "pip install webrtcvad-wheels")
        self.margin_min = margin_min
        self.margin_max = margin_max
        self.hysteresis = hysteresis

        self._tail = np.zeros(0, dtype=np.float32)
        self._vad_frames = deque(maxlen=VAD_WINDOW)
        self._recent = deque(maxlen=FLOOR_WINDOW)
        self._floor_db = None
        self._peak_db = -120.0

        self.in_speech = False
        self.speech_total = 0.0
        self.silence_run = 0.0
        self.speech_run = 0.0
        self.last_db = -120.0
        self.vad_hit = False

    @property
    def floor_db(self):
        # Без стелі: вона недооцінювала фон у шумних кімнатах, поріг падав під
        # рівень шуму і запис не зупинявся. Замість неї — прив'язка до піку.
        return self._floor_db if self._floor_db is not None else ABS_MIN_DB

    @property
    def threshold_db(self):
        floor = self.floor_db
        span = self._peak_db - floor
        margin = float(np.clip(0.4 * span, self.margin_min, self.margin_max))
        enter = floor + margin
        # Поріг зобов'язаний бути нижче робочого рівня голосу, інакше тихе
        # мовлення без паузи (фон калібрується на сам голос) обривається.
        if self._peak_db > ABS_MIN_DB:
            enter = min(enter, self._peak_db - PEAK_HEADROOM_DB)
        enter = max(enter, ABS_MIN_DB)
        return enter - self.hysteresis if self.in_speech else enter

    def _update_levels(self, block):
        self._recent.append(float(np.mean(block ** 2)))
        if len(self._recent) == FLOOR_WINDOW:
            window_db = 10.0 * np.log10(float(np.mean(self._recent)) + 1e-18)
            self._floor_db = (window_db if self._floor_db is None
                              else min(self._floor_db, window_db))
        self._peak_db = max(self.last_db, self._peak_db - PEAK_DECAY_DB)

    def _webrtc_speech(self, block):
        """Мажоритарне рішення по вікну ~480 мс: сирий webrtcvad дає близько
        10% ложних спрацювань, і одиничний хибний кадр скидав би паузу."""
        if self.vad is None:
            return False
        buf = np.concatenate([self._tail, block])
        n = len(buf) // WEBRTC_FRAME
        for i in range(n):
            frame = buf[i * WEBRTC_FRAME:(i + 1) * WEBRTC_FRAME]
            pcm = np.clip(frame * 32767.0, -32768, 32767).astype(np.int16)
            try:
                self._vad_frames.append(
                    1 if self.vad.is_speech(pcm.tobytes(), SAMPLE_RATE) else 0
                )
            except Exception:
                self.vad = None
                return False
        self._tail = buf[n * WEBRTC_FRAME:]
        if not self._vad_frames:
            return False
        return (sum(self._vad_frames) / len(self._vad_frames)) >= VAD_RATIO

    def push(self, block):
        dur = len(block) / SAMPLE_RATE
        self.last_db = dbfs(block)
        self._update_levels(block)

        energy = self.last_db > self.threshold_db
        self.vad_hit = self._webrtc_speech(block)
        # VAD враховується лише якщо сигнал помітно вище фону.
        vad_ok = self.vad_hit and self.last_db > self.floor_db + VAD_MIN_OVER_FLOOR
        speech = energy or vad_ok

        if speech:
            self.in_speech = True
            self.speech_total += dur
            self.speech_run += dur
            self.silence_run = 0.0
        else:
            self.in_speech = False
            self.speech_run = 0.0
            if self.speech_total > 0:
                self.silence_run += dur

    @property
    def armed(self):
        """Чи можна обривати — тобто чи щось уже реально було сказано."""
        return self.speech_total >= 0.35


# --------------------------------------------------------------------------

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
        from model_service import RemoteModel, factory
        m = (factory(name, compute, backend, device) if one_shot else
             RemoteModel(name, compute, backend=backend, device=device))
        holder["model"] = m
    except Exception as exc:
        holder["error"] = exc
        emit(f"[error] модель: {exc}", tty)
    finally:
        ready.set()


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


def read_history():
    try:
        entries = json.loads(HISTORY.read_text())
        if not isinstance(entries, list) or any(
            not isinstance(e, dict) or not isinstance(e.get("text"), str)
            for e in entries
        ):
            raise ValueError("Некоректний формат історії")
        return entries
    except FileNotFoundError:
        return []


def save_history(text, complete=True):
    entries = read_history()
    entries.append({"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                    "text": text, "complete": complete})
    HISTORY.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".dictate-history-", dir=HISTORY.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(entries[-50:], f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(name, HISTORY)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def latest_text():
    return next((e["text"] for e in reversed(read_history())
                 if e.get("complete", True) and e.get("kind") != "prompt"), "")


def calibrate(seconds, gate_kwargs, device):
    gate = SpeechGate(**gate_kwargs)
    rec = Recorder(gate, device)
    print(f"WebRTC VAD: {'є' if gate.vad else 'НЕМА (тільки енергетичний)'}")
    print("Говори нормальним голосом, потім помовч 5 секунд.\n")
    try:
        while rec.elapsed() < seconds:
            time.sleep(0.1)
            sys.stderr.write(meter(gate, rec.elapsed(), True))
            sys.stderr.flush()
    except KeyboardInterrupt:
        pass
    rec.finish()
    print(f"\n\nмовлення всього: {gate.speech_total:.1f}s, "
          f"фон {gate.floor_db:.1f} dB, пік {gate._peak_db:.1f} dB")
    print("Під час мовлення має бути МОВЛЕННЯ, у паузах — пауза.")
    print("  мовлення читається як пауза  -> зменш --margin-min")
    print("  тиша читається як мовлення   -> збільш --margin-min "
          "або --aggressiveness 3, або --vad energy")


def parse_args(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model", default=os.environ.get("DICTATE_MODEL",
                                                     "large-v3-turbo"))
    p.add_argument("--compute", default=os.environ.get("DICTATE_COMPUTE",
                                                       "auto"))
    p.add_argument("--lang", default=os.environ.get("DICTATE_LANG", "uk"))
    p.add_argument("--beam", type=int, default=1)
    p.add_argument("--silence", type=float,
                   default=float(os.environ.get("DICTATE_SILENCE", "0")),
                   help="секунд тишi до автостопу; 0 = тільки ручний стоп")
    p.add_argument("--partial-silence", type=float, default=1.2,
                   help="пауза, по якій нарізається сегмент для лайв-виводу")
    p.add_argument("--max", type=float, default=600.0)
    p.add_argument("--max-lead", type=float, default=20.0,
                   help="кинути, якщо за цей час не почулось нічого")
    p.add_argument("--device", default=None,
                   help="індекс або назва мікрофона (див. --list-devices)")
    p.add_argument("--list-devices", action="store_true")
    p.add_argument("--vad", choices=["auto", "webrtc", "energy"],
                   default="auto")
    p.add_argument("--aggressiveness", type=int, default=2, choices=[0, 1, 2, 3])
    p.add_argument("--margin-min", type=float, default=6.0)
    p.add_argument("--margin-max", type=float, default=12.0)
    p.add_argument("--hysteresis", type=float, default=4.0)
    p.add_argument("--paste", action="store_true")
    p.add_argument("--stdout", action="store_true")
    p.add_argument("--live", dest="live", action="store_true", default=True,
                   help="фонове розпізнавання під час запису (увімкнене типово)")
    p.add_argument("--no-live", dest="live", action="store_false")
    p.add_argument("--calibrate", type=float, metavar="SECONDS", default=None)
    p.add_argument("--copy-last", action="store_true", help="скопіювати останній повний текст")
    p.add_argument("--append", action="store_true", help="додиктувати до останнього повного тексту")
    p.add_argument("--history", action="store_true", help="показати останні 50 транскриптів")
    p.add_argument("--one-shot", action="store_true", help="звільнити модель після запису")
    p.add_argument("--model-status", action="store_true", help="стан фонової моделі")
    p.add_argument("--unload-model", action="store_true", help="звільнити GPU після диктування")
    p.add_argument("--overlay", action="store_true", help="тимчасовий індикатор запису поверх вікон")
    p.add_argument("--backend", choices=["auto", "faster-whisper", "mlx"], default=os.environ.get("DICTATE_BACKEND", "auto"))
    p.add_argument("--inference-device", choices=["auto", "cpu", "cuda", "metal"], default=os.environ.get("DICTATE_INFERENCE_DEVICE", "auto"))
    a = p.parse_args(argv)
    if (a.silence < 0 or a.partial_silence < 0 or a.max <= 0
            or a.max_lead <= 0 or a.beam < 1):
        p.error("часові межі та beam повинні мати коректні додатні значення")
    return a


def main():
    a = parse_args()
    if a.model_status or a.unload_model:
        from model_service import control
        try:
            print(json.dumps(control("shutdown" if a.unload_model else "status"), ensure_ascii=False))
        except (OSError, EOFError) as exc:
            sys.exit(f"Модель зайнята або недоступна: {exc}")
        return
    if a.history or a.copy_last:
        try:
            if a.history:
                print(json.dumps(read_history(), ensure_ascii=False, indent=2))
                return
            text = latest_text()
            if not text:
                notify("Історія поки порожня")
                return
            if not to_clipboard(text):
                notify("Не вдалося скопіювати текст", "critical")
                sys.exit(1)
            notify("✓ Останній текст скопійовано")
            return
        except (OSError, ValueError) as exc:
            sys.exit(f"Історія: {exc}")

    if a.list_devices:
        import sounddevice as sd
        print(sd.query_devices())
        return

    device = a.device
    if device is not None and device.isdigit():
        device = int(device)

    tty = sys.stderr.isatty()

    gate_kwargs = dict(mode=a.vad, margin_min=a.margin_min,
                       margin_max=a.margin_max, hysteresis=a.hysteresis,
                       aggressiveness=a.aggressiveness)

    if a.calibrate:
        calibrate(a.calibrate, gate_kwargs, device)
        return

    if try_stop_running():          # той самий хоткей вдруге = стоп
        sys.exit(0)

    # Keep ownership through transcription and clipboard delivery, too.
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    try:
        session_lock = SessionLock(SOCK + ".lock")
    except BlockingIOError:
        notify("⏳ Попередній запис ще обробляється")
        return
    atexit.register(session_lock.close)
    try:
        base_text = latest_text() if a.append else ""
    except (OSError, ValueError) as exc:
        sys.exit(f"Історія: {exc}")

    stop_event = threading.Event()
    srv = stop_listener(stop_event)

    gate = SpeechGate(**gate_kwargs)
    try:
        rec = Recorder(gate, device)
    except Exception as exc:
        emit(f"[error] мікрофон: {exc}", tty)
        notify(f"Мікрофон: {exc}", "critical")
        srv.close()
        if os.path.exists(SOCK):
            os.unlink(SOCK)
        sys.exit(1)

    from overlay import Overlay
    overlay = Overlay(a.overlay, a.lang)
    atexit.register(overlay.close)
    notify("● Запис")
    if tty:
        emit("\033[1m● МІКРОФОН УВІМКНЕНО\033[0m  "
             f"(vad={'webrtc' if gate.vad else 'energy'}, "
             f"стоп: {a.silence or '—'}s тишi або Ctrl+C)", tty)

    holder, ready = {}, threading.Event()
    threading.Thread(target=load_model, daemon=True,
                     args=(holder, ready, a.model, a.compute, tty, a.one_shot, a.backend, a.inference_device)).start()

    scribe = Transcriber(holder, ready, a, tty)
    scribe.start()

    cut_at = 0
    speech_at_cut = 0.0
    warned = False
    reason = "max"
    try:
        while not stop_event.is_set():
            time.sleep(0.05)
            if tty:
                with _out_lock:
                    sys.stderr.write(meter(gate, rec.elapsed(), ready.is_set()))
                    sys.stderr.flush()

            overlay.update(elapsed=rec.elapsed(), level=float(np.clip((gate.last_db + 60) / 55, 0, 1)))
            if rec.elapsed() > a.max:
                break
            if not gate.armed and rec.elapsed() > a.max_lead:
                reason = "lead"
                break

            # Діагностика залипання: "мовлення" без жодної паузи хвилину —
            # майже завжди означає, що шум читається як голос.
            if not warned and gate.speech_run > STUCK_WARN_S:
                warned = True
                emit("[warn] мовлення не вщухає — схоже, шум читається як "
                     "голос. Ctrl+C, потім `--calibrate 20` і підніми "
                     "--margin-min.", tty)

            # Нарізка сегмента по паузі: транскрипція йде у фоні, поки
            # ти говориш далі.
            if (a.live and a.partial_silence
                    and gate.silence_run >= a.partial_silence
                    and gate.speech_total - speech_at_cut >= 0.8):
                audio, total = rec.slice_from(cut_at)
                if len(audio) >= SAMPLE_RATE * 0.4:
                    scribe.submit(audio)
                    cut_at = total
                    speech_at_cut = gate.speech_total

            if a.silence and gate.armed and gate.silence_run >= a.silence:
                reason = "silence"
                break
        else:
            reason = "manual"
    except KeyboardInterrupt:
        reason = "interrupt"
    finally:
        srv.close()
        if os.path.exists(SOCK):
            os.unlink(SOCK)

    full = rec.finish()
    overlay.update(state="transcribing")
    if tty:
        emit(f"\033[1m■ Стоп\033[0m ({reason}), "
             f"{len(full)/SAMPLE_RATE:.1f}s аудіо, "
             f"{gate.speech_total:.1f}s мовлення", tty)

    if reason == "lead" or gate.speech_total < 0.35:
        notify("Нічого не почулось")
        scribe.close()
        sys.exit(0)

    tail = full[cut_at:]
    if len(tail) >= SAMPLE_RATE * 0.4:
        scribe.submit(tail)
    scribe.close()

    if not ready.is_set():
        notify("⏳ Дочекайся моделі")
        if tty:
            emit("[wait] модель ще вантажиться…", tty)
    notify("⏳ Завершую розпізнавання")
    scribe.join()
    if not a.one_shot and "model" in holder:
        holder["model"].close()

    if "error" in holder:
        notify(f"Модель: {holder['error']}", "critical")
        sys.exit(1)

    text = " ".join(scribe.parts).strip()
    if not text and scribe.errors:
        notify("Не вдалося розпізнати запис; буфер не змінено", "critical")
        sys.exit(1)
    if not text:
        emit("[warn] порожній транскрипт", tty)
        notify("Тиша")
        sys.exit(0)

    if base_text:
        text = base_text.rstrip() + "\n\n" + text
    try:
        save_history(text, complete=not scribe.errors)
    except (OSError, ValueError) as exc:
        emit(f"[error] не вдалося зберегти історію: {exc}", tty)
        notify("Не вдалося зберегти історію", "critical")
    if scribe.errors:
        print(text)
        notify("Текст неповний: помилка розпізнавання. Перевір --history; буфер не змінено", "critical")
        sys.exit(1)

    ok = to_clipboard(text)
    if a.paste and ok:
        try:
            do_paste()
        except Exception as exc:
            emit(f"[paste] {exc}; text is still in clipboard", tty)
    if a.stdout or not tty:
        print(text)
    if tty:
        emit("\n\033[1m" + text + "\033[0m", tty)
        emit("[buffer] " + ("у буфері" if ok
                            else "копіювання не вдалося — текст є в історії та на екрані"), tty)
    overlay.close()
    notify(f"✓ {len(text)} симв. у буфері" if ok else "✓ Готово (без буфера)")


if __name__ == "__main__":
    main()
