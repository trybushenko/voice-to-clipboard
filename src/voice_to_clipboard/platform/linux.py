"""X11 integration. Wayland deliberately uses desktop bindings and manual paste."""
import os
import subprocess
import threading
import time


def focus_probe():
    if os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('Wayland: paste manually using the desktop clipboard')
    import json
    import queue
    from pathlib import Path
    from Xlib.display import Display
    display = Display()
    try:
        process = subprocess.Popen(['/usr/bin/python3', str(Path(__file__).with_name('atspi_probe.py'))],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                               text=True, start_new_session=True)
    except Exception:
        display.close()
        raise
    replies = queue.Queue()
    def read():
        for line in process.stdout:
            replies.put(line)
        replies.put(None)
    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    first = [True]
    def snapshot():
        if not first[0]:
            process.stdin.write('check\n'); process.stdin.flush()
        first[0] = False
        try:
            line = replies.get(timeout=2.5)
        except queue.Empty:
            raise RuntimeError('Accessibility field check timed out; paste manually')
        if not line:
            raise RuntimeError('Install python3-gi and gir1.2-atspi-2.0 for safe field detection')
        response = json.loads(line)
        if response.get('ok') is not True:
            raise RuntimeError(response.get('error', 'Focused field changed; paste manually'))
        focus = display.get_input_focus().focus
        return getattr(focus, 'id', None)
    def close():
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=.5)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait(timeout=1)
        reader.join(timeout=.2)
        process.stdin.close(); process.stdout.close()
        display.close()
    snapshot.close = close
    return snapshot


def send_paste(expected, guard):
    from Xlib.display import Display
    from Xlib import XK
    from Xlib.ext import xtest
    from Xlib import X
    display = Display()
    try:
        modifiers = [display.keysym_to_keycode(XK.string_to_keysym(name)) for name in
                     ('Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R', 'Super_L', 'Super_R')]
        deadline = time.monotonic() + 2
        while True:
            bits = display.query_keymap()
            if not any(code and bits[code // 8] & (1 << (code % 8)) for code in modifiers):
                break
            guard.check()
            if time.monotonic() >= deadline:
                raise RuntimeError('Release modifiers and paste manually; text is in clipboard')
            time.sleep(.02)
        actual = subprocess.run(['xclip', '-selection', 'clipboard', '-o'], capture_output=True,
                                timeout=2, check=True).stdout.decode('utf-8')
        if actual != expected:
            raise RuntimeError('Clipboard changed; restore text with dictate --copy-last')
        guard.check()
        ctrl = display.keysym_to_keycode(XK.string_to_keysym('Control_L'))
        v = display.keysym_to_keycode(XK.string_to_keysym('v'))
        if not ctrl or not v:
            raise RuntimeError('Paste keys unavailable; paste manually')
        # No --clearmodifiers: never release the user's held keys.
        xtest.fake_input(display, X.KeyPress, ctrl)
        xtest.fake_input(display, X.KeyPress, v)
        xtest.fake_input(display, X.KeyRelease, v)
        xtest.fake_input(display, X.KeyRelease, ctrl)
        display.sync()
    finally:
        display.close()


class NativeHotkeys(threading.Thread):
    def __init__(self, callbacks, modifiers='alt+shift'):
        super().__init__(daemon=True)
        self.callbacks = callbacks
        self.modifiers = modifiers
        self.stopping = threading.Event()
        self.ready = threading.Event()
        self.error = None

    def start(self):
        super().start()
        if not self.ready.wait(5):
            self.stop()
            raise RuntimeError('X11 hotkey registration timed out')
        if self.error:
            self.join(timeout=2)
            raise self.error

    def stop(self):
        self.stopping.set()

    def run(self):
        from Xlib import X, XK, error
        from Xlib.display import Display
        display = None
        grabbed = []
        try:
            display = Display()
            root = display.screen().root
            masks = {'alt': X.Mod1Mask, 'ctrl': X.ControlMask, 'shift': X.ShiftMask, 'win': X.Mod4Mask}
            modifiers = sum(masks[name] for name in self.modifiers.split('+'))
            callbacks = {}
            errors = []
            num = display.keysym_to_keycode(XK.string_to_keysym('Num_Lock'))
            num_mask = 0
            for index, codes in enumerate(display.get_modifier_mapping()):
                if num in codes and num:
                    num_mask |= 1 << index
            for key, callback in self.callbacks.items():
                code = display.keysym_to_keycode(XK.string_to_keysym(key))
                if not code:
                    raise RuntimeError(f'X11 key unavailable: {key}')
                callbacks[code] = callback
                for extra in set((0, X.LockMask, num_mask, X.LockMask | num_mask)):
                    mask = modifiers | extra
                    root.grab_key(code, mask, False, X.GrabModeAsync, X.GrabModeAsync,
                                  onerror=lambda *args: errors.append(True))
                    grabbed.append((code, mask))
                display.sync()
                if errors:
                    raise RuntimeError(f'Hotkey {self.modifiers}+{key} is already assigned. '
                                       'Use desktop bindings OR voice-hotkeys, not both.')
            self.ready.set()
            down = set()
            while not self.stopping.wait(.01):
                while display.pending_events():
                    event = display.next_event()
                    if event.type == X.KeyPress and event.detail in callbacks:
                        if event.detail not in down:
                            down.add(event.detail)
                            callbacks[event.detail]()
                    elif event.type == X.KeyRelease:
                        # X11 auto-repeat emits release/press pairs while physically held.
                        bits = display.query_keymap()
                        if not bits[event.detail // 8] & (1 << (event.detail % 8)):
                            down.discard(event.detail)
        except Exception as exc:
            self.error = exc
        finally:
            if display is not None:
                for code, mask in grabbed:
                    display.screen().root.ungrab_key(code, mask)
                display.sync(); display.close()
            self.ready.set()


def wayland_hint():
    try:
        result = subprocess.run(['gdbus', 'call', '--session', '--dest', 'org.freedesktop.portal.Desktop',
                                 '--object-path', '/org/freedesktop/portal/desktop', '--method',
                                 'org.freedesktop.DBus.Properties.Get',
                                 'org.freedesktop.portal.GlobalShortcuts', 'version'],
                                capture_output=True, text=True, timeout=2)
        available = result.returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        available = False
    return ('GlobalShortcuts portal is exposed, but this host does not yet bind through it. '
            if available else 'GlobalShortcuts portal was not detected. ') + (
            'Configure dictate commands in desktop Keyboard Settings; paste manually on Wayland.')
