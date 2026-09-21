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
from .core.session import SOCK, GLOBAL_LOCK, try_stop_running, stop_listener
from .core.history import read_history, save_history, latest_text
from .core.transcription import Transcriber, load_model
from .ui.terminal import emit, meter, _out_lock

def calibrate(seconds, gate_kwargs, device):
    gate = SpeechGate(**gate_kwargs)
    rec = Recorder(gate, device)
    print(f"WebRTC VAD: {'available' if gate.vad else 'unavailable (energy only)'}")
    print("Speak normally, then remain silent for 5 seconds.\n")
    try:
        while rec.elapsed() < seconds:
            time.sleep(0.1)
            sys.stderr.write(meter(gate, rec.elapsed(), True))
            sys.stderr.flush()
    except KeyboardInterrupt:
        pass
    rec.finish()
    print(f"\n\ntotal speech: {gate.speech_total:.1f}s, "
          f"noise floor {gate.floor_db:.1f} dB, peak {gate._peak_db:.1f} dB")
    print("Expect SPEECH while speaking and pause during silence.")
    print("  speech detected as silence -> decrease --margin-min")
    print("  silence detected as speech -> increase --margin-min "
          "or use --aggressiveness 3, or --vad energy")


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
                   help="seconds of silence before automatic stop; 0 = manual stop only")
    p.add_argument("--partial-silence", type=float, default=1.2,
                   help="pause length that triggers a live transcription segment")
    p.add_argument("--max", type=float, default=600.0)
    p.add_argument("--max-lead", type=float, default=20.0,
                   help="stop if no speech is detected within this many seconds")
    p.add_argument("--device", default=None,
                   help="microphone index or name (see --list-devices)")
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
                   help="transcribe in the background while recording (enabled by default)")
    p.add_argument("--no-live", dest="live", action="store_false")
    p.add_argument("--calibrate", type=float, metavar="SECONDS", default=None)
    p.add_argument("--copy-last", action="store_true", help="copy the last full transcript")
    p.add_argument("--append", action="store_true", help="append dictation to the last full transcript")
    p.add_argument("--history", action="store_true", help="show the last 50 transcripts")
    p.add_argument("--one-shot", action="store_true", help="unload the model after recording")
    p.add_argument("--model-status", action="store_true", help="show background model status")
    p.add_argument("--unload-model", action="store_true", help="unload the model to release GPU memory")
    p.add_argument("--overlay", action="store_true", help="show a temporary recording overlay")
    p.add_argument("--backend", choices=["auto", "faster-whisper", "mlx"], default=os.environ.get("DICTATE_BACKEND", "auto"))
    p.add_argument("--inference-device", choices=["auto", "cpu", "cuda", "metal"], default=os.environ.get("DICTATE_INFERENCE_DEVICE", "auto"))
    a = p.parse_args(argv)
    if (a.silence < 0 or a.partial_silence < 0 or a.max <= 0
            or a.max_lead <= 0 or a.beam < 1):
        p.error("time limits and beam must have valid positive values")
    return a


def main():
    configure_text_output()
    a = parse_args()
    if a.model_status or a.unload_model:
        from .worker.client import control
        try:
            print(json.dumps(control("shutdown" if a.unload_model else "status"), ensure_ascii=False))
        except (OSError, EOFError) as exc:
            sys.exit(f"Model is busy or unavailable: {exc}")
        return
    if a.history or a.copy_last:
        try:
            if a.history:
                print(json.dumps(read_history(), ensure_ascii=False, indent=2))
                return
            text = latest_text()
            if not text:
                notify("History is empty")
                return
            if not to_clipboard(text):
                notify("Could not copy text", "critical")
                sys.exit(1)
            notify("✓ Last transcript copied")
            return
        except (OSError, ValueError) as exc:
            sys.exit(f"History: {exc}")

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
    from .core.session_status import publish
    if try_stop_running():          # той самий хоткей вдруге = стоп
        sys.exit(0)

    # Keep ownership through transcription and clipboard delivery, too.
    os.makedirs(os.path.dirname(SOCK), exist_ok=True)
    try:
        session_lock = SessionLock(GLOBAL_LOCK)
    except BlockingIOError:
        publish("error", "Another dictation is active; finish it before starting a new recording")
        notify("⏳ The previous recording is still being processed")
        return
    atexit.register(session_lock.close)
    paste_guard = None
    if a.paste:
        from .platform.focus import make_guard
        paste_guard = make_guard()
        atexit.register(paste_guard.close)
    try:
        base_text = latest_text() if a.append else ""
    except (OSError, ValueError) as exc:
        sys.exit(f"History: {exc}")

    srv = stop_listener(stop_event)

    gate = SpeechGate(**gate_kwargs)
    try:
        rec = Recorder(gate, device)
    except Exception as exc:
        publish("error", "Microphone unavailable. Check the selected device and microphone permission.")
        emit(f"[error] microphone: {exc}", tty)
        notify(f"Microphone: {exc}", "critical")
        srv.close()
        if os.path.exists(SOCK):
            remove_endpoint(Path(SOCK))
        sys.exit(1)

    from .ui.overlay import Overlay
    overlay = Overlay(a.overlay, a.lang)
    atexit.register(overlay.close)
    publish("recording", "Microphone is recording")
    notify("● Recording")
    if tty:
        emit("\033[1m● MICROPHONE ON\033[0m  "
             f"(vad={'webrtc' if gate.vad else 'energy'}, "
             f"stop: {a.silence or '—'}s of silence or Ctrl+C)", tty)

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
                emit("[warn] continuous speech detected; background noise may be treated as "
                     "speech. Press Ctrl+C, then run `--calibrate 20` and increase "
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
    publish("transcribing", "Finishing transcription")
    overlay.update(state="transcribing")
    if tty:
        emit(f"\033[1m■ Stopped\033[0m ({reason}), "
             f"{len(full)/SAMPLE_RATE:.1f}s audio, "
             f"{gate.speech_total:.1f}s speech", tty)

    if reason == "lead" or gate.speech_total < 0.35:
        publish("delivered", "No speech detected; clipboard unchanged")
        notify("No speech detected")
        scribe.close()
        sys.exit(0)

    tail = full[cut_at:]
    if len(tail) >= SAMPLE_RATE * 0.4:
        scribe.submit(tail)
    scribe.close()

    if not ready.is_set():
        notify("⏳ Waiting for the model")
        if tty:
            emit("[wait] model is still loading…", tty)
    notify("⏳ Finishing transcription")
    while scribe.is_alive():
        scribe.join(timeout=.1)
    if not a.one_shot and "model" in holder:
        holder["model"].close()

    if "error" in holder:
        publish("error", "Model unavailable. Check model/backend settings and run System check.")
        notify(f"Model: {holder['error']}", "critical")
        sys.exit(1)

    text = " ".join(scribe.parts).strip()
    if not text and scribe.errors:
        publish("error", "Transcription failed; clipboard unchanged")
        notify("Could not transcribe the recording; clipboard unchanged", "critical")
        sys.exit(1)
    if not text:
        emit("[warn] empty transcript", tty)
        publish("delivered", "No speech detected; clipboard unchanged")
        notify("Silence")
        sys.exit(0)

    if base_text:
        text = base_text.rstrip() + "\n\n" + text
    try:
        save_history(text, complete=not scribe.errors)
    except (OSError, ValueError) as exc:
        emit(f"[error] could not save history: {exc}", tty)
        notify("Could not save history", "critical")
    if scribe.errors:
        publish("error", "Incomplete transcription saved in history; clipboard unchanged")
        print(text)
        notify("Incomplete transcript: transcription failed. Check --history; clipboard unchanged", "critical")
        sys.exit(1)

    ok = to_clipboard(text)
    delivery = "Copied to clipboard" if ok else "Copy failed; transcript saved in history"
    if a.paste and ok:
        try:
            do_paste(text, paste_guard)
            delivery = "Paste shortcut sent"
        except Exception as exc:
            delivery = str(exc)
            emit(f"[paste] {delivery}", tty)
    if a.stdout or not tty:
        print(text)
    if tty:
        emit("\n\033[1m" + text + "\033[0m", tty)
        emit("[buffer] " + ("copied to clipboard" if ok
                            else "copy failed; text is available in history and on screen"), tty)
    if paste_guard is not None:
        paste_guard.close()
    publish("delivered" if ok else "error",
            "Paste shortcut sent" if delivery == "Paste shortcut sent" else
            "Copied to clipboard; paste manually" if ok else "Clipboard failed; transcript saved in history")
    emit(f"[delivery] {delivery}", tty)
    if a.overlay:
        overlay.update(state="result", message=delivery)
        time.sleep(2)
    overlay.close()
    notify(delivery)

