"""Track the original paste destination; failures preserve clipboard-only delivery."""
import json
import os
import sys
import threading
import time


class FocusGuard:
    def __init__(self, probe, expected=None, interval=.05):
        if sys.platform == "win32":
            import comtypes  # Initialize module on caller, not the event-handler MTA thread.
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
            self.error = f'{type(exc).__name__}: {exc}'
        finally:
            self.ready.set()
            if 'probe' in locals() and hasattr(probe, 'close'):
                probe.close()

    def invalidate(self):
        self.changed = True

    def check(self):
        if self.error or self.changed or not self.thread.is_alive():
            raise RuntimeError('Paste target changed or cannot be verified. Text is in clipboard; paste manually. ' +
                               (self.error or ('Focus changed' if self.changed else 'Focus monitor stopped')))
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
    comtypes.CoInitializeEx(0)  # UI Automation event subscriptions require a non-UI MTA.
    automation = None
    handler = None
    try:
        module = GetModule('UIAutomationCore.dll')
        automation = CreateObject(module.CUIAutomation, interface=module.IUIAutomation)
        user = ctypes.WinDLL('user32', use_last_error=True)
        user.GetForegroundWindow.restype = ctypes.c_void_p
        initial = [None]
        invalid = threading.Event()
        invalid_reason = ['']
        def identity(element):
            if not element or element.CurrentIsPassword:
                return None
            runtime = element.GetRuntimeId()
            return list(runtime) if runtime is not None else None
        class Handler(comtypes.COMObject):
            _com_interfaces_ = [module.IUIAutomationFocusChangedEventHandler]
            def HandleFocusChangedEvent(self, sender):
                try:
                    received = identity(sender)
                    if initial[0] is not None and received != initial[0]:
                        invalid_reason[0] = (f'event {received!r} class={sender.CurrentClassName!r} has_focus={sender.CurrentHasKeyboardFocus!r}; '
                                             f'initial={initial[0]!r}; current={identity(automation.GetFocusedElement())!r}')
                        invalid.set()
                except Exception as exc:
                    invalid_reason[0] = f'{type(exc).__name__}: {exc}'
                    invalid.set()
                return 0
        handler = Handler()
        # Establish baseline before subscribing; a final snapshot also checks for a
        # change during subscription. The handler invalidates even if focus returns.
        initial[0] = identity(automation.GetFocusedElement())
        automation.AddFocusChangedEventHandler(None, handler)
        def snapshot():
            if invalid.is_set():
                raise RuntimeError('UIA focus event: ' + invalid_reason[0])
            window = user.GetForegroundWindow()
            current = identity(automation.GetFocusedElement())
            if not window:
                raise RuntimeError('Windows has no foreground window')
            if not current:
                raise RuntimeError('UIA focused field has no usable runtime identity (or is a password field)')
            if current != initial[0]:
                raise RuntimeError('UIA focused field differs from the initial field')
            return [int(window), current]
        def close():
            nonlocal automation, handler
            try:
                automation.RemoveFocusChangedEventHandler(handler)
            finally:
                handler = None
                automation = None
                comtypes.CoUninitialize()
        snapshot.close = close
        return snapshot
    except Exception:
        automation = None
        comtypes.CoUninitialize()
        raise


def capture_windows_target():
    guard = FocusGuard(windows_probe)
    try:
        return guard.target if not guard.error and not guard.changed else None
    finally:
        guard.close()


def make_guard(local=False):
    if not local and os.environ.get("DICTATE_PASTE_TOKEN"):
        return RemoteGuard(os.environ["DICTATE_PASTE_TOKEN"], os.environ["DICTATE_CONTROL_PATH"])
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


class RemoteGuard:
    """Ask the original host monitor; never recapture a new destination in a child."""
    def __init__(self, token, path):
        self.token, self.path = token, path
    def check(self):
        from ..core.host_control import request
        try:
            result = request(self.path, 'check-paste', token=self.token)
            if result.get('ok') is not True:
                raise RuntimeError('Paste destination was not confirmed')
        except (OSError, EOFError, ValueError, RuntimeError) as exc:
            raise RuntimeError(f'Original paste target changed or host unavailable. Text is in clipboard; paste manually. {exc}') from exc
    def close(self):
        pass
