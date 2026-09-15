"""Command-line interface and dictation session orchestration."""
import argparse
import atexit
import json
import os
from pathlib import Path
from .platform.files import remove_endpoint
import sys
import threading
import time
import numpy as np
from .platform.desktop import SessionLock, notify, to_clipboard, do_paste, configure_text_output
from .core.speech_gate import SAMPLE_RATE, STUCK_WARN_S, SpeechGate
from .core.recording import Recorder
from .core.lifecycle import stop_on_interrupt
from .core.session import SOCK, try_stop_running, stop_listener
from .core.history import read_history, save_history, latest_text
from .core.transcription import Transcriber, load_model
from .ui.terminal import emit, meter, _out_lock

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
    configure_text_output()
    a = parse_args()
    if a.model_status or a.unload_model:
        from .worker.client import control
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

    stop_event = threading.Event()
    with stop_on_interrupt(stop_event):
        record(a, device, tty, gate_kwargs, stop_event)


def record(a, device, tty, gate_kwargs, stop_event):
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

    srv = stop_listener(stop_event)

    gate = SpeechGate(**gate_kwargs)
    try:
        rec = Recorder(gate, device)
    except Exception as exc:
        emit(f"[error] мікрофон: {exc}", tty)
        notify(f"Мікрофон: {exc}", "critical")
        srv.close()
        if os.path.exists(SOCK):
            remove_endpoint(Path(SOCK))
        sys.exit(1)

    from .ui.overlay import Overlay
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
            remove_endpoint(Path(SOCK))

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
    while scribe.is_alive():
        scribe.join(timeout=.1)
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

