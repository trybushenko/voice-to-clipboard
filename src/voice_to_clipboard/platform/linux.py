"""X11 integration. Wayland deliberately uses desktop bindings and manual paste."""
import os
import subprocess
import threading
import time


def focus_probe():
    if os.environ.get('WAYLAND_DISPLAY'):
        raise RuntimeError('Wayland does not expose a safe paste destination')
    from Xlib.display import Display
    from pynput import keyboard, mouse
    display = Display()
    changes = [0]
    def click(x, y, button, pressed):
        if pressed:
            changes[0] += 1
    def key(key):
        # Navigation/typing may move the caret or select another field.
        if key in (keyboard.Key.tab, keyboard.Key.enter, keyboard.Key.esc,
                   keyboard.Key.up, keyboard.Key.down, keyboard.Key.left, keyboard.Key.right,
                   keyboard.Key.home, keyboard.Key.end, keyboard.Key.page_up, keyboard.Key.page_down):
            changes[0] += 1
    pointer = mouse.Listener(on_click=click, on_scroll=lambda *args: click(0, 0, None, True))
    keys = keyboard.Listener(on_press=key)
    pointer.start(); keys.start()
    def snapshot():
        focus = display.get_input_focus().focus
        identifier = getattr(focus, 'id', 0)
        if not identifier or not pointer.is_alive() or not keys.is_alive():
            return None
        return [identifier, changes[0]]
    def close():
        pointer.stop(); keys.stop()
        pointer.join(timeout=.3); keys.join(timeout=.3)
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
