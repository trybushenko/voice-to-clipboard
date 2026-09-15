"""Selective Windows global hotkeys; no global keyboard suppression."""
import ctypes
from ctypes import wintypes
import threading

WM_HOTKEY = 0x0312
MOD_NOREPEAT = 0x4000
MODIFIERS = {'alt': 1, 'ctrl': 2, 'shift': 4, 'win': 8}


def parse_modifiers(value):
    if not isinstance(value, str):
        raise ValueError('Hotkey modifiers must be text')
    names = value.lower().split('+')
    if not names or len(set(names)) != len(names) or any(n not in MODIFIERS for n in names):
        raise ValueError('Use modifiers such as alt+shift or ctrl+alt+shift')
    return sum(MODIFIERS[n] for n in names)


def user_api():
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    api.RegisterHotKey.restype = wintypes.BOOL
    api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    api.UnregisterHotKey.restype = wintypes.BOOL
    api.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND,
                                 wintypes.UINT, wintypes.UINT, wintypes.UINT]
    api.PeekMessageW.restype = wintypes.BOOL
    return api


class NativeHotkeys(threading.Thread):
    def __init__(self, callbacks, modifiers='alt+shift', api_factory=user_api):
        super().__init__(daemon=True)
        self.callbacks = dict(callbacks)
        self.modifiers = parse_modifiers(modifiers)
        self.label = modifiers
        self.api_factory = api_factory
        self.ready = threading.Event()
        self.stopping = threading.Event()
        self.error = None

    def start(self):
        super().start()
        if not self.ready.wait(5):
            self.stop()
            raise RuntimeError('Windows hotkey registration timed out')
        if self.error:
            self.join(timeout=2)
            raise self.error

    def stop(self):
        self.stopping.set()

    def run(self):
        registered = []
        api = None
        try:
            api = self.api_factory()
            actions = {}
            for identifier, (key, callback) in enumerate(self.callbacks.items(), 1):
                if not api.RegisterHotKey(None, identifier, self.modifiers | MOD_NOREPEAT, ord(key.upper())):
                    raise RuntimeError(f'Cannot register {self.label}+{key.upper()}: shortcut unavailable. '
                                       'Close the other hotkey host or choose --hotkey-modifiers ctrl+alt+shift.')
                registered.append(identifier)
                actions[identifier] = callback
            self.ready.set()
            message = wintypes.MSG()
            while not self.stopping.is_set():
                # Bounded polling keeps stop/Ctrl+C responsive without posting to another thread.
                for _ in range(64):
                    if not api.PeekMessageW(ctypes.byref(message), None, 0, 0, 1):
                        break
                    if message.message == WM_HOTKEY and message.wParam in actions:
                        actions[message.wParam]()
                    if self.stopping.is_set():
                        break
                self.stopping.wait(.01)
        except Exception as exc:
            self.error = exc
        finally:
            if api is not None:
                for identifier in registered:
                    api.UnregisterHotKey(None, identifier)
            self.ready.set()


def layout_conflict(modifiers):
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Keyboard Layout\Toggle') as key:
            value = winreg.QueryValueEx(key, 'Hotkey')[0]
    except OSError:
        return False
    chosen = set(modifiers.split('+'))
    return (value == '1' and {'alt', 'shift'} <= chosen) or (value == '2' and {'ctrl', 'shift'} <= chosen)
