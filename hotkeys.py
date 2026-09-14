"""Portable global hotkey host. Children own microphone and clipboard sessions."""
import argparse
import subprocess
import sys
import threading
import time


def main():
    parser = argparse.ArgumentParser(description='Keep running to enable Alt+Shift+U/E/L dictation shortcuts.')
    parser.add_argument('--no-overlay', action='store_true')
    parser.add_argument('--inference-device', choices=['auto', 'cpu', 'cuda', 'metal'], default='auto')
    parser.add_argument('--model', default=None)
    args = parser.parse_args()
    from pynput import keyboard
    from platform_support import SessionLock, cache_dir
    try:
        lock = SessionLock(cache_dir() / 'dictate-hotkeys.lock')
    except BlockingIOError:
        sys.exit('Hotkeys are already running')
    children = []
    last_launch = 0.0
    guard = threading.Lock()

    def launch(lang, paste=False):
        nonlocal last_launch
        with guard:
            now = time.monotonic()
            if now - last_launch < .4:
                return
            last_launch = now
            children[:] = [p for p in children if p.poll() is None]
            cmd = [sys.executable, '-m', 'dictate', '--lang', lang, '--silence', '0', '--inference-device', args.inference_device]
            if args.model:
                cmd += ['--model', args.model]
            if lang == 'en':
                cmd += ['--beam', '5']
            if paste:
                cmd.append('--paste')
            if not args.no_overlay:
                cmd.append('--overlay')
            children.append(subprocess.Popen(cmd))

    print('Ready: Alt+Shift+U Ukrainian | Alt+Shift+E English | Alt+Shift+L Ukrainian + paste. Ctrl+C to quit.')
    try:
        with keyboard.GlobalHotKeys({'<alt>+<shift>+u': lambda: launch('uk'),
                                     '<alt>+<shift>+e': lambda: launch('en'),
                                     '<alt>+<shift>+l': lambda: launch('uk', True)}) as listener:
            try:
                listener.join()
            except KeyboardInterrupt:
                listener.stop()
    finally:
        lock.close()


if __name__ == '__main__':
    main()
