"""Single-process tray/menu-bar UI around the existing hotkey/session controller."""
import argparse
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
from ..core.host_control import request
from ..platform.paths import cache_dir
from ..platform.processes import spawn_background


def endpoint():
    return cache_dir() / 'dictate-hotkey-control.sock'


def show_error(message):
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()
    messagebox.showerror('Voice to Clipboard', message, parent=root)
    root.destroy()


def linux_bindings():
    if not sys.platform.startswith('linux'):
        return
    # Prefer the current venv; use matching distro GI only as a fallback.
    try:
        import gi
    except ImportError:
        system = '/usr/lib/python3/dist-packages'
        if Path(system).is_dir():
            sys.path.append(system)
        try:
            import gi
        except ImportError as exc:
            raise RuntimeError('Linux desktop needs Python GI/GTK bindings. Install python3-gi gir1.2-gtk-3.0 and use the matching system Python venv.') from exc
    if 'PYSTRAY_BACKEND' not in os.environ:
        for namespace in ('AppIndicator3', 'AyatanaAppIndicator3'):
            try:
                gi.require_version(namespace, '0.1')
                os.environ['PYSTRAY_BACKEND'] = 'appindicator'
                break
            except ValueError:
                continue
        else:
            gi.require_version('Gtk', '3.0')
            os.environ['PYSTRAY_BACKEND'] = 'gtk'


class Bridge:
    def __init__(self, logger):
        self.logger = logger
        self.snapshot = {'state': 'paused', 'phase': 'starting', 'message': 'Starting', 'dictation_processes': 0}
        self.lock = threading.Lock()
        self.panel = None
        self.panels = []
        self.done = threading.Event()
        self.actions = queue.Queue(maxsize=16)
        self.icon = None

    def update(self, value):
        with self.lock:
            previous = (self.snapshot.get('phase'), self.snapshot.get('state'), self.snapshot.get('message'))
            current = (value.get('phase'), value.get('state'), value.get('message'))
            self.snapshot = dict(value)
        if previous != current:
            self.logger.info('State=%s hotkeys=%s message=%s', *current)

    def status(self):
        with self.lock:
            return dict(self.snapshot)

    def show_panel(self):
        # A singleton panel has its own lock and foregrounds itself on relaunch.
        if self.panel is not None and self.panel.poll() is None:
            try:
                request(cache_dir() / 'dictate-panel.sock', 'show')
                return
            except (OSError, EOFError, RuntimeError):
                pass
        self.panels[:] = [p for p in self.panels if p.poll() is None]
        self.panel = spawn_background([sys.executable, '-m', 'voice_to_clipboard.ui.desktop_panel'],
                                      no_console=True, stdin=subprocess.DEVNULL,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.panels.append(self.panel)

    def submit(self, operation):
        try:
            self.actions.put_nowait(operation)
        except queue.Full:
            self.logger.warning('Tray action queue is full')

    def action_loop(self):
        while not self.done.is_set():
            try:
                operation = self.actions.get(timeout=.2)
            except queue.Empty:
                continue
            try:
                if operation == 'panel':
                    self.show_panel()
                elif operation == 'autostart':
                    from ..platform.launchers import enabled, set_enabled
                    set_enabled(not enabled())
                    self.logger.info('Autostart preference updated')
                    self.icon.update_menu()
                elif isinstance(operation, tuple):
                    request(endpoint(), 'start-profile', key=operation[1])
                elif operation == 'log':
                    from .desktop_panel import open_log
                    open_log()
                else:
                    request(endpoint(), operation)
            except Exception as exc:
                self.logger.error('Action %s failed: %s', operation, exc)
                self.update({**self.status(), 'message': str(exc)})
                self.show_panel()


def image_for(state):
    from PIL import Image, ImageDraw
    color = {'recording': '#ed5353', 'transcribing': '#f2b544', 'error': '#ec7b36',
             'paused': '#77808c', 'disabled': '#77808c', 'shutting-down': '#77808c'}.get(state, '#3182ce')
    image = Image.new('RGBA', (64, 64))
    draw = ImageDraw.Draw(image)
    draw.ellipse((2, 2, 62, 62), fill=color)
    draw.rounded_rectangle((25, 12, 39, 36), radius=7, fill='white')
    draw.arc((19, 23, 45, 45), 0, 180, fill='white', width=3)
    draw.line((32, 43, 32, 52), fill='white', width=3)
    draw.line((25, 52, 39, 52), fill='white', width=3)
    return image


def run():
    from ..core.app_logging import configure, LogStream
    from ..core.desktop_settings import arguments
    from ..platform.desktop import SessionLock
    try:
        ownership = SessionLock(cache_dir() / 'dictate-desktop.lock')
    except BlockingIOError:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                request(endpoint(), 'show')
                return
            except (OSError, EOFError, RuntimeError):
                time.sleep(.1)
        show_error('Desktop app is still starting. Try again shortly.')
        return
    logger = configure()
    streams = sys.stdout, sys.stderr
    sys.stdout = sys.stderr = LogStream(logger)
    os.environ['DICTATE_BACKGROUND'] = '1'
    bridge = Bridge(logger)
    host = None
    try:
        if sys.platform == 'win32':
            import comtypes  # Initialize before the host's MTA focus threads.
        linux_bindings()
        import pystray
        if not pystray.Icon.HAS_MENU:
            raise RuntimeError('This Linux tray backend has no menus. Install python3-gi and an AppIndicator/GTK tray host; see the desktop setup guide.')
        host_arguments = arguments()
        # Release an idle legacy model before allocating a desktop-owned one.
        # The global session lock prevents interrupting an active CLI recording.
        from ..core.session import GLOBAL_LOCK
        try:
            with SessionLock(GLOBAL_LOCK):
                from ..worker.client import control as model_control
                model_control('shutdown')
        except (OSError, RuntimeError, EOFError):
            logger.info('Legacy model is busy or unavailable; leaving it alone')
        from ..platform.launchers import enabled
        from ..core.profiles import label
        from ..core.settings import read_settings
        first_run = not read_settings()
        item = pystray.MenuItem
        def action(operation):
            return lambda icon, entry: bridge.submit(operation)
        def idle(entry):
            status = bridge.status()
            return status.get('dictation_processes', 0) == 0 and status.get('phase') != 'shutting-down'
        menu = pystray.Menu(
            item(lambda entry: 'Status: ' + bridge.status().get('phase', 'starting'), action('panel'), default=True),
            item('Start recording (clipboard)', pystray.Menu(lambda:
                tuple(item(label(p), action(('profile', p['key'])), enabled=idle)
                      for p in bridge.status().get('profiles', [])))),
            item('Stop recording', action('stop-recording'), enabled=lambda entry: bridge.status().get('phase') in ('starting', 'recording')),
            item('Pause shortcuts', action('pause'), checked=lambda entry: bridge.status().get('state') == 'paused'),
            item('Resume shortcuts', action('resume')),
            item('Copy last transcript', action('copy-last')),
            pystray.Menu.SEPARATOR,
            item('Settings / System check', action('panel')),
            item('Open log', action('log')),
            item('Start at login', action('autostart'), checked=lambda entry: enabled()),
            item('Cancel unfinished dictation and exit', action('cancel'), visible=lambda entry: bridge.status().get('phase') == 'shutting-down'),
            item('Quit (finish dictation first)', action('quit')))
        icon = bridge.icon = pystray.Icon('voice-to-clipboard', image_for('idle'), 'Voice to Clipboard', menu)
        if sys.platform.startswith('linux') and os.environ.get('PYSTRAY_BACKEND') == 'gtk':
            from gi.repository import GLib
            def verify_tray():
                # pystray 0.19 GTK StatusIcon is not embedded on some GNOME desktops.
                if not icon._status_icon.is_embedded():
                    logger.warning('No GTK tray host; opening the control panel. Install AppIndicator support for a persistent icon.')
                    bridge.submit('panel')
                return False
            GLib.timeout_add(2000, verify_tray)
        def host_main():
            from .hotkeys import main
            try:
                main(host_arguments, desktop=bridge)
            except BaseException as exc:
                logger.exception('Desktop controller stopped: %s', exc)
                bridge.update({'state': 'paused', 'phase': 'error', 'message': str(exc), 'dictation_processes': 0})
            finally:
                bridge.done.set()
                icon.stop()
        def setup(icon):
            nonlocal host
            icon.visible = True
            host = threading.Thread(target=host_main, name='dictation-controller')
            host.start()
            threading.Thread(target=bridge.action_loop, daemon=True).start()
            if first_run:
                bridge.submit('panel')
            previous = None
            while not bridge.done.wait(.25):
                status = bridge.status()
                phase = status.get('phase', 'idle')
                label = 'paused' if status.get('state') == 'paused' and phase == 'idle' else phase
                current = (label, status.get('message'), repr(status.get('profiles')))
                if current != previous:
                    icon.icon = image_for(label)
                    icon.title = ('Voice to Clipboard — ' + label + ': ' + status.get('message', ''))[:120]
                    icon.update_menu()
                    previous = current
        icon.run(setup=setup)  # macOS requires the native event loop on the main thread.
    except Exception as exc:
        logger.exception('Desktop startup failed')
        show_error(str(exc))
    finally:
        if host is not None and host.is_alive():
            try:
                request(endpoint(), 'quit')
            except (OSError, RuntimeError, EOFError):
                pass
            host.join(timeout=130)
        bridge.done.set()
        if any(panel.poll() is None for panel in bridge.panels):
            try:
                request(cache_dir() / 'dictate-panel.sock', 'quit')
            except (OSError, EOFError, RuntimeError):
                pass
        for panel in bridge.panels:
            if panel.poll() is None:
                try:
                    panel.wait(timeout=3)
                    continue
                except subprocess.TimeoutExpired:
                    panel.terminate()
                try:
                    panel.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    panel.kill()
                    panel.wait(timeout=2)
        sys.stdout, sys.stderr = streams
        ownership.close()
        logger.info('Desktop application exited')
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)


def main():
    parser = argparse.ArgumentParser(description='Voice to Clipboard desktop app and per-user launcher setup')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--install', action='store_true', help='Install a per-user Start Menu/.app/.desktop launcher')
    group.add_argument('--uninstall', action='store_true', help='Remove our launcher and autostart; preserve user data')
    group.add_argument('--run', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    from ..platform.launchers import install, uninstall
    if args.install:
        print(install())
        return
    if args.uninstall:
        uninstall()
        return
    try:
        status = request(endpoint(), 'status')
    except (OSError, EOFError, ValueError, RuntimeError):
        status = None
    if status is not None:
        if status.get('desktop'):
            if 'profiles' not in status:
                show_error('An older Voice to Clipboard host is still running. Quit it from the tray, then launch the updated app. Installing an update does not restart a running host.')
                return
            request(endpoint(), 'show')
            return
        if status.get('dictation_processes'):
            show_error('Finish the current dictation before switching from voice-hotkeys to the desktop app.')
            return
        request(endpoint(), 'quit')
        deadline = time.monotonic() + 10
        while endpoint().exists() and time.monotonic() < deadline:
            time.sleep(.1)
        if endpoint().exists():
            show_error('The previous hotkey host is still stopping. Try again shortly.')
            return
    if args.run:
        run()
        return
    spawn_background([sys.executable, '-m', 'voice_to_clipboard.ui.desktop_app', '--run'],
                     no_console=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == '__main__':
    main()
