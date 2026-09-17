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
    import json
    import queue
    from ..platform.desktop import configure_text_output, SessionLock, cache_dir
    from ..core.settings import read_modifiers, save_modifiers
    from ..core.hotkey_session import SessionLauncher
    from ..core.host_control import ControlServer, ListenerController, request
    from ..platform.windows_hotkeys import parse_modifiers
    configure_text_output()
    parser = argparse.ArgumentParser(description='Global U/E/L dictation shortcuts. Ctrl+C quits after draining recording.')
    parser.add_argument('--no-overlay', action='store_true')
    parser.add_argument('--inference-device', choices=['auto', 'cpu', 'cuda', 'metal'], default='auto')
    parser.add_argument('--model', default=None)
    parser.add_argument('--hotkey-modifiers', help='Modifiers for U/E/L, e.g. ctrl+alt; saved after successful registration')
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--background', action='store_true', help='Start a console-independent host and return')
    for operation in ('pause', 'resume', 'status', 'stop-recording', 'quit'):
        commands.add_argument('--' + operation, dest='operation', action='store_const', const=operation,
                              help='Control the running hotkey host: ' + operation)
    args = parser.parse_args()
    endpoint = cache_dir() / 'dictate-hotkey-control.sock'
    if args.operation:
        try:
            print(json.dumps(request(endpoint, args.operation), ensure_ascii=False))
        except (OSError, EOFError, ValueError, RuntimeError) as exc:
            sys.exit(f'Hotkey host unavailable or request failed: {exc}. Start voice-hotkeys first.')
        return
    if args.background:
        from ..platform.background import start
        try:
            print(json.dumps(start([arg for arg in sys.argv[1:] if arg != '--background'], endpoint)))
        except (OSError, RuntimeError) as exc:
            sys.exit(str(exc))
        return
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
    def enqueue(action):
        if not quitting.is_set():
            try:
                actions.put_nowait(action)
            except queue.Full:
                pass
    def create_listener(callbacks):
        if sys.platform == 'win32':
            from ..platform.windows_hotkeys import NativeHotkeys
            return NativeHotkeys(callbacks, args.hotkey_modifiers)
        if sys.platform == 'darwin':
            from ..platform.macos import listener as create
            return create(callbacks, args.hotkey_modifiers)
        from ..platform.linux import NativeHotkeys
        return NativeHotkeys(callbacks, args.hotkey_modifiers)
    controller = ListenerController(create_listener, enqueue)
    control = None
    def handle(payload):
        operation = payload["op"]
        if operation == "check-paste":
            return launcher.check_paste(payload.get("token"))
        if operation == 'pause':
            controller.pause()
            print('Hotkeys paused; active dictation continues. Use --resume or --stop-recording.', flush=True)
        elif operation == 'resume':
            controller.resume()
            print('Hotkeys resumed.', flush=True)
        elif operation == 'stop-recording':
            if launcher.children:
                launcher.pending_stop = True
                launcher.tick()
            else:
                try_stop_running()
        elif operation == 'quit':
            quitting.set()
        return {'state': 'stopping' if quitting.is_set() else 'paused' if controller.paused else 'listening',
                'pid': os.getpid(),
                'dictation_processes': sum(p.poll() is None for p in launcher.children)}
    try:
        controller.resume()
        control = ControlServer(endpoint)
        if explicit:
            save_modifiers(args.hotkey_modifiers)
        print(f'Ready: {args.hotkey_modifiers}+U Ukrainian | +E English | +L Ukrainian + paste. Ctrl+C to quit.', flush=True)
        try:
            while not quitting.is_set():
                control.dispatch(handle)
                if quitting.is_set():
                    break
                if not controller.paused and not controller.listener.is_alive():
                    break
                try:
                    generation, lang, paste = actions.get(timeout=.1)
                    if controller.accepts(generation):
                        launcher.launch(lang, paste)
                except queue.Empty:
                    launcher.tick()
                except OSError as exc:
                    print(f'Cannot start/stop dictation: {exc}', flush=True)
        except KeyboardInterrupt:
            print('Stopping hotkeys…', flush=True)
    finally:
        quitting.set()
        try:
            if control is not None:
                control.close()
            controller.pause()
        finally:
            try:
                drain_children(launcher.children)
            finally:
                launcher.close()
                lock.close()
    if getattr(controller.listener, 'error', None):
        sys.exit(str(controller.listener.error))
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
