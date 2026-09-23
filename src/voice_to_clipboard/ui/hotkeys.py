"""Portable global hotkey host. Children own microphone and clipboard sessions."""
import argparse
import subprocess
import sys
import threading
import time
from ..platform.processes import spawn_background
from ..core.session import try_stop_running


def main(argv=None, desktop=None):
    import os
    import json
    import queue
    from ..platform.desktop import configure_text_output, SessionLock, cache_dir
    from ..core.settings import read_modifiers, save_modifiers
    from ..core.hotkey_session import SessionLauncher
    from ..core.host_control import ControlServer, ListenerController, request
    from ..platform.windows_hotkeys import parse_modifiers
    configure_text_output()
    parser = argparse.ArgumentParser(description='Configured language-profile shortcuts. Ctrl+C quits after draining recording.')
    parser.add_argument('--no-overlay', action='store_true')
    parser.add_argument('--inference-device', choices=['auto', 'cpu', 'cuda', 'metal'], default='auto')
    parser.add_argument('--model', default=None)
    parser.add_argument('--hotkey-modifiers', help='Default modifiers for profiles without an override, e.g. ctrl+alt; saved after successful registration')
    commands = parser.add_mutually_exclusive_group()
    commands.add_argument('--background', action='store_true', help='Start a console-independent host and return')
    for operation in ('pause', 'resume', 'status', 'stop-recording', 'quit'):
        commands.add_argument('--' + operation, dest='operation', action='store_const', const=operation,
                              help='Control the running hotkey host: ' + operation)
    args = parser.parse_args(argv)
    args.desktop = desktop is not None
    from ..core.desktop_settings import load as load_desktop_settings
    from ..core.settings import save_settings
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
        initial_settings = load_desktop_settings()
        args.profiles = initial_settings['profiles']
        onboarding_complete = initial_settings['onboarding_complete']
        args.hotkey_modifiers = args.hotkey_modifiers or read_modifiers()
        parse_modifiers(args.hotkey_modifiers)
        args.hotkey_modifiers = args.hotkey_modifiers.lower()
    except (ValueError, RuntimeError, OSError) as exc:
        parser.error(str(exc))
    wayland = sys.platform.startswith('linux') and os.environ.get('WAYLAND_DISPLAY')
    if wayland and desktop is None:
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
    cancel = threading.Event()
    listener_error = ['']
    def enqueue(action):
        if not quitting.is_set():
            try:
                actions.put_nowait(action)
            except queue.Full:
                pass
    def create_listener(callbacks):
        modifiers = {p['key']: p.get('modifiers') or args.hotkey_modifiers for p in args.profiles}
        if sys.platform == 'win32':
            from ..platform.windows_hotkeys import NativeHotkeys
            return NativeHotkeys(callbacks, modifiers)
        if sys.platform == 'darwin':
            from ..platform.macos import listener as create
            return create(callbacks, modifiers)
        from ..platform.linux import NativeHotkeys
        return NativeHotkeys(callbacks, modifiers)
    controller = ListenerController(create_listener, enqueue, lambda: args.profiles)
    control = None
    def status():
        return {'state': 'stopping' if quitting.is_set() else 'paused' if controller.paused else 'listening',
                'desktop': desktop is not None, 'pid': os.getpid(),
                'phase': 'shutting-down' if quitting.is_set() else 'disabled' if controller.paused and launcher.state == 'idle' else launcher.state,
                'worker_pid': launcher.worker.pid if launcher.worker is not None and launcher.worker.poll() is None else None,
                'message': listener_error[0] or launcher.message,
                'profiles': args.profiles,
                'profile_modifiers': True,
                'onboarding_supported': True,
                'onboarding_complete': onboarding_complete,
                'hotkey_modifiers': args.hotkey_modifiers,
                'dictation_processes': sum(p.poll() is None for p in launcher.children)}
    def handle(payload):
        nonlocal onboarding_complete
        operation = payload["op"]
        if operation == 'cancel':
            if quitting.is_set():
                cancel.set()
            return status()
        if quitting.is_set() and operation not in ('status', 'quit', 'check-paste'):
            raise RuntimeError('Application is finishing dictation; wait or cancel from the tray')
        if operation == 'show' and desktop is not None:
            desktop.show_panel()
        if operation == 'settings':
            if desktop is None:
                raise RuntimeError('Start the desktop app to change settings')
            launcher.tick()
            if launcher.children:
                raise RuntimeError('Finish dictation before changing settings')
            values = payload.get('values')
            from ..core.desktop_settings import validate
            from ..core.settings import save_settings
            values = validate({**load_desktop_settings(), **values}) if isinstance(values, dict) else validate(values)
            old = (args.hotkey_modifiers, args.model, args.inference_device, args.no_overlay, args.profiles)
            paused = controller.paused
            controller.pause()
            try:
                args.profiles = values['profiles']
                args.hotkey_modifiers = values['hotkey_modifiers']
                args.model = values['model'] or None
                args.inference_device = values['inference_device']
                args.no_overlay = not values['overlay']
                if not wayland and (not paused or (args.hotkey_modifiers != old[0] or args.profiles != old[4])):
                    controller.resume()  # Verify changed registrations, without requiring permissions for unrelated settings.
                    if paused:
                        controller.pause()
                save_settings(values)
                onboarding_complete = values['onboarding_complete']
                if wayland:
                    listener_error[0] = 'Wayland: use desktop shortcuts or tray recording; paste manually'
                elif not controller.paused:
                    listener_error[0] = ''
            except Exception:
                controller.pause()
                args.hotkey_modifiers, args.model, args.inference_device, args.no_overlay, args.profiles = old
                if not paused:
                    controller.resume()
                raise
        if operation == 'start-profile':
            profile = next((p for p in args.profiles if p['key'] == payload.get('key')), None)
            if profile is None:
                raise ValueError('Profile no longer exists; reopen Settings')
            launcher.launch(profile['language'], False, model=profile['model'])
        if operation in ('start-uk', 'start-en'):
            language = 'uk' if operation == 'start-uk' else 'en'
            profile = next((p for p in args.profiles if p['language'] == language), None)
            if profile is None:
                raise ValueError('Add this language in Settings first')
            launcher.launch(language, model=profile['model'])
        if operation == 'copy-last':
            from ..core.history import latest_text
            from ..platform.desktop import to_clipboard
            text = latest_text()
            if not text or not to_clipboard(text):
                raise RuntimeError('No saved transcript, or clipboard unavailable')
        if operation == "check-paste":
            return launcher.check_paste(payload.get("token"))
        if operation == 'pause':
            controller.pause()
            print('Hotkeys paused; active dictation continues. Use --resume or --stop-recording.', flush=True)
        elif operation == 'resume':
            if wayland:
                raise RuntimeError('Wayland: configure shortcuts in desktop settings; tray recording remains available')
            controller.resume()
            listener_error[0] = ''
            print('Hotkeys resumed.', flush=True)
        elif operation == 'stop-recording':
            if launcher.children:
                launcher.pending_stop = True
                launcher.tick()
            elif desktop is None:
                try_stop_running()
        elif operation == 'quit':
            quitting.set()
        return status()
    try:
        try:
            if wayland:
                raise RuntimeError('Wayland: use desktop shortcuts or tray recording; paste manually')
            controller.resume()
        except Exception as exc:
            if desktop is None:
                raise
            listener_error[0] = str(exc)
        control = ControlServer(endpoint)
        if explicit:
            save_modifiers(args.hotkey_modifiers)
        from ..core.settings import read_settings
        from ..platform.paths import data_dir
        # Remember a new installation before its first recording creates history.
        # Otherwise history-only legacy detection would introduce U/E/L on restart.
        fresh_install = not read_settings() and not (data_dir() / 'history.json').exists()
        if desktop is None or fresh_install:
            save_settings({'schema_version': 3, 'profiles': args.profiles})
        print('Ready: ' + ' | '.join((p.get('modifiers') or args.hotkey_modifiers) + '+' + p['key'].upper() +
              ' ' + p['language'] + (' + paste' if p['paste'] else '') for p in args.profiles), flush=True)
        try:
            while not quitting.is_set():
                control.dispatch(handle)
                launcher.tick()
                if desktop is not None:
                    desktop.update(status())
                if quitting.is_set():
                    break
                if not controller.paused and not controller.listener.is_alive():
                    if desktop is None:
                        break
                    listener_error[0] = str(getattr(controller.listener, 'error', '') or 'Hotkeys stopped. Use Resume or Settings.')
                    controller.pause()
                try:
                    generation, lang, paste = actions.get(timeout=.1)
                    if controller.accepts(generation):
                        profile = lang
                        launcher.launch(profile['language'], profile['paste'], model=profile['model'])
                except queue.Empty:
                    launcher.tick()
                except (OSError, RuntimeError) as exc:
                    launcher.state, launcher.message = 'error', str(exc)
                    print(f'Cannot start/stop dictation: {exc}', flush=True)
        except KeyboardInterrupt:
            print('Stopping hotkeys…', flush=True)
    finally:
        quitting.set()
        try:
            controller.pause()
            if desktop is None:
                if control is not None:
                    control.close()
                    control = None
                drain_children(launcher.children)
            else:
                deadline = time.monotonic() + 120
                while any(p.poll() is None for p in launcher.children):
                    if control is not None:
                        control.dispatch(handle)
                    desktop.update(status())
                    launcher.stop_running()
                    if cancel.is_set() or time.monotonic() >= deadline:
                        desktop.logger.warning('Shutdown cancelled unfinished dictation after cancellation/deadline')
                        break
                    time.sleep(.1)
        finally:
            try:
                if desktop is not None:
                    launcher.shutdown()
                else:
                    launcher.close()
            finally:
                if control is not None:
                    control.close()
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
