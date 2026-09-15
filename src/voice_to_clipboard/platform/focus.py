"""Track the original paste destination; failures preserve clipboard-only delivery."""
import json
import os
import sys
import threading
import time


class FocusGuard:
    def __init__(self, probe, expected=None, interval=.05):
        self.probe = probe
        self.interval = interval
        self.stopping = threading.Event()
        self.changed = False
        self.error = None
        self.target = expected
        self.observed = threading.Condition()
        self.sequence = 0
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._watch, daemon=True)
        self.thread.start()
        if not self.ready.wait(3):
            self.error = 'Could not identify the focused field'

    def _watch(self):
        # Probe initialization and all calls stay on one thread (COM/AX ownership).
        try:
            probe = self.probe()
            current = probe()
            if current is None:
                raise RuntimeError('Focused field is unavailable')
            if self.target is None:
                self.target = current
            elif current != self.target:
                self.changed = True
            self.ready.set()
            while not self.stopping.wait(self.interval):
                if probe() != self.target:
                    self.changed = True
                with self.observed:
                    self.sequence += 1
                    self.observed.notify_all()
        except Exception as exc:
            self.error = str(exc)
        finally:
            self.ready.set()
            if 'probe' in locals() and hasattr(probe, 'close'):
                probe.close()

    def invalidate(self):
        self.changed = True

    def check(self):
        if self.error or self.changed or not self.thread.is_alive():
            raise RuntimeError('Paste target changed or cannot be verified. Text is in clipboard; paste manually')
        with self.observed:
            sequence = self.sequence
            fresh = self.observed.wait_for(lambda: self.sequence > sequence or self.error, timeout=1)
        if not fresh or self.error or self.changed:
            raise RuntimeError('Paste target changed or verification timed out. Text is in clipboard; paste manually')

    def close(self):
        self.stopping.set()
        self.thread.join(timeout=.3)


def windows_probe():
    import ctypes
    import comtypes
    from comtypes.client import CreateObject, GetModule
    comtypes.CoInitialize()
    module = GetModule('UIAutomationCore.dll')
    automation = CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
    user = ctypes.WinDLL('user32', use_last_error=True)
    user.GetForegroundWindow.restype = ctypes.c_void_p
    def snapshot():
        window = user.GetForegroundWindow()
        element = automation.GetFocusedElement()
        if not window or not element or element.CurrentIsPassword:
            return None
        runtime = element.GetRuntimeId()
        if runtime is None:
            return None
        return [int(window), list(runtime)]
    snapshot.close = comtypes.CoUninitialize
    return snapshot


def capture_windows_target():
    guard = FocusGuard(windows_probe)
    try:
        return guard.target if not guard.error and not guard.changed else None
    finally:
        guard.close()


def make_guard():
    if sys.platform == 'win32':
        raw = os.environ.get('DICTATE_PASTE_TARGET')
        expected = json.loads(raw) if raw else None
        # Explicit null from host means capture failed, not permission to retarget.
        if raw == 'null':
            return UnavailableGuard()
        return FocusGuard(windows_probe, expected)
    if sys.platform == 'darwin':
        from .macos import focus_probe
        return FocusGuard(focus_probe)
    if not os.environ.get('WAYLAND_DISPLAY'):
        from .linux import focus_probe
        return FocusGuard(focus_probe)
    return UnavailableGuard()


class UnavailableGuard:
    def check(self):
        raise RuntimeError('Safe field verification is unavailable; text is in clipboard. Paste manually')
    def close(self):
        pass
