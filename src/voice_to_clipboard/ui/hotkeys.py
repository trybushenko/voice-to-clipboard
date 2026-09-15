"""Portable global hotkey host. Children own microphone and clipboard sessions."""
import argparse
import subprocess
import sys
import threading
import time
from ..platform.processes import spawn_background
from ..core.session import try_stop_running


def main():
    from voice_to_clipboard.platform.desktop import configure_text_output
    configure_text_output()
    parser = argparse.ArgumentParser(description='Keep running to enable Alt+Shift+U/E/L dictation shortcuts.')
    parser.add_argument('--no-overlay', action='store_true')
    parser.add_argument('--inference-device', choices=['auto', 'cpu', 'cuda', 'metal'], default='auto')
    parser.add_argument('--model', default=None)
    args = parser.parse_args()
    from pynput import keyboard
    from voice_to_clipboard.platform.desktop import SessionLock, cache_dir
    try:
        lock = SessionLock(cache_dir() / 'dictate-hotkeys.lock')
    except BlockingIOError:
        sys.exit('Hotkeys are already running')
    children = []
    last_launch = 0.0
    quitting = threading.Event()
    guard = threading.Lock()

    def launch(lang, paste=False):
        nonlocal last_launch
        with guard:
            if quitting.is_set():
                return
            now = time.monotonic()
            if now - last_launch < .4:
                return
            last_launch = now
            children[:] = [p for p in children if p.poll() is None]
            cmd = [sys.executable, '-m', 'voice_to_clipboard', '--lang', lang, '--silence', '0', '--inference-device', args.inference_device]
            if args.model:
                cmd += ['--model', args.model]
            if lang == 'en':
                cmd += ['--beam', '5']
            if paste:
                cmd.append('--paste')
            if not args.no_overlay:
                cmd.append('--overlay')
            children.append(spawn_background(cmd))

    print('Ready: Alt+Shift+U Ukrainian | Alt+Shift+E English | Alt+Shift+L Ukrainian + paste. Ctrl+C to quit.')
    listener = keyboard.GlobalHotKeys({'<alt>+<shift>+u': lambda: launch('uk'),
                                       '<alt>+<shift>+e': lambda: launch('en'),
                                       '<alt>+<shift>+l': lambda: launch('uk', True)})
    try:
        listener.start()
        try:
            while listener.is_alive():
                time.sleep(.1)
        except KeyboardInterrupt:
            print('Stopping hotkeys…', flush=True)
        finally:
            quitting.set()
            listener.stop()
            listener.join(timeout=2)
        with guard:
            active = [p for p in children if p.poll() is None]
        drain_children(active)
    finally:
        lock.close()
    print('Hotkeys stopped.', flush=True)


def drain_children(children, timeout=900):
    """Stop and drain owned dictation children; second Ctrl+C explicitly cancels."""
    if not children:
        return
    print('Finishing dictation and copying text. Ctrl+C again cancels.', flush=True)
    deadline = time.monotonic() + timeout
    try:
        while any(p.poll() is None for p in children):
            # A child may still be starting and not have published its endpoint.
            try_stop_running()
            if time.monotonic() >= deadline:
                print('Dictation is still running; hotkeys stopped. '
                      'Use dictate to stop recording, or manage its process explicitly.', flush=True)
                return
            time.sleep(.1)
    except KeyboardInterrupt:
        for process in children:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        print('Dictation cancelled; unfinished text was not copied.', flush=True)


if __name__ == '__main__':
    main()
