"""Portable global hotkey host. Children own microphone and clipboard sessions."""
import argparse
import subprocess
import sys
import threading
import time
from ..platform.processes import spawn_background
from ..core.session import try_stop_running


def main():
    import os
    import queue
    from ..platform.desktop import configure_text_output, SessionLock, cache_dir
    from ..core.settings import read_modifiers, save_modifiers
    from ..core.hotkey_session import SessionLauncher
    from ..platform.windows_hotkeys import parse_modifiers
    configure_text_output()
    parser = argparse.ArgumentParser(description='Global U/E/L dictation shortcuts. Ctrl+C quits after draining recording.')
    parser.add_argument('--no-overlay', action='store_true')
    parser.add_argument('--inference-device', choices=['auto', 'cpu', 'cuda', 'metal'], default='auto')
    parser.add_argument('--model', default=None)
    parser.add_argument('--hotkey-modifiers', help='Modifiers for U/E/L, e.g. ctrl+alt; saved after successful registration')
    args = parser.parse_args()
    explicit = args.hotkey_modifiers is not None
    try:
        args.hotkey_modifiers = args.hotkey_modifiers or read_modifiers()
        parse_modifiers(args.hotkey_modifiers)
        args.hotkey_modifiers = args.hotkey_modifiers.lower()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    if sys.platform.startswith('linux') and os.environ.get('WAYLAND_DISPLAY'):
        from ..platform.linux import wayland_hint
        parser.error('Wayland: ' + wayland_hint())
    if sys.platform == 'win32':
        from ..platform.windows_hotkeys import layout_conflict
        if layout_conflict(args.hotkey_modifiers):
            print('Alt/Shift conflicts with the Windows layout switch setting. '
                  'Use --hotkey-modifiers ctrl+alt, or change the system shortcut yourself.', flush=True)
    try:
        lock = SessionLock(cache_dir() / 'dictate-hotkeys.lock')
    except BlockingIOError:
        sys.exit('Hotkeys are already running')
    launcher = SessionLauncher(args)
    actions = queue.Queue(maxsize=8)
    quitting = threading.Event()
    def enqueue(lang, paste=False):
        if not quitting.is_set():
            try:
                actions.put_nowait((lang, paste))
            except queue.Full:
                pass
    callbacks = {'u': lambda: enqueue('uk'), 'e': lambda: enqueue('en'),
                 'l': lambda: enqueue('uk', True)}
    listener = None
    try:
        if sys.platform == 'win32':
            from ..platform.windows_hotkeys import NativeHotkeys
            listener = NativeHotkeys(callbacks, args.hotkey_modifiers)
        elif sys.platform == 'darwin':
            from ..platform.macos import listener as create_listener
            listener = create_listener(callbacks, args.hotkey_modifiers)
        else:
            from ..platform.linux import NativeHotkeys
            listener = NativeHotkeys(callbacks, args.hotkey_modifiers)
        listener.start()
        if explicit:
            save_modifiers(args.hotkey_modifiers)
        print(f'Ready: {args.hotkey_modifiers}+U Ukrainian | +E English | +L Ukrainian + paste. Ctrl+C to quit.', flush=True)
        try:
            while listener.is_alive():
                try:
                    lang, paste = actions.get(timeout=.1)
                    launcher.launch(lang, paste)
                except queue.Empty:
                    launcher.tick()
                except OSError as exc:
                    print(f'Cannot start/stop dictation: {exc}', flush=True)
        except KeyboardInterrupt:
            print('Stopping hotkeys…', flush=True)
    finally:
        quitting.set()
        if listener is not None:
            listener.stop()
            if listener.ident is not None:
                listener.join(timeout=2)
        try:
            drain_children(launcher.children)
        finally:
            lock.close()
    if getattr(listener, 'error', None):
        sys.exit(str(listener.error))
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
