"""Native Windows paste, with pointer-size-correct INPUT structures."""
import ctypes as c
import time

DWORD, WORD, LONG, ULONG_PTR = c.c_uint32, c.c_uint16, c.c_int32, c.c_size_t


class KEYBDINPUT(c.Structure):
    _fields_ = [('wVk', WORD), ('wScan', WORD), ('dwFlags', DWORD),
                ('time', DWORD), ('dwExtraInfo', ULONG_PTR)]


class MOUSEINPUT(c.Structure):
    _fields_ = [('dx', LONG), ('dy', LONG), ('mouseData', DWORD),
                ('dwFlags', DWORD), ('time', DWORD), ('dwExtraInfo', ULONG_PTR)]


class HARDWAREINPUT(c.Structure):
    _fields_ = [('uMsg', DWORD), ('wParamL', WORD), ('wParamH', WORD)]


class INPUTUNION(c.Union):
    _fields_ = [('ki', KEYBDINPUT), ('mi', MOUSEINPUT), ('hi', HARDWAREINPUT)]


class INPUT(c.Structure):
    _anonymous_ = ('data',)
    _fields_ = [('type', DWORD), ('data', INPUTUNION)]


def api():
    user = c.WinDLL('user32', use_last_error=True)
    user.SendInput.argtypes = [c.c_uint, c.POINTER(INPUT), c.c_int]
    user.SendInput.restype = c.c_uint
    user.GetAsyncKeyState.argtypes = [c.c_int]
    user.GetAsyncKeyState.restype = c.c_short
    user.GetForegroundWindow.restype = c.c_void_p
    return user


def modifiers_down(user):
    return any(user.GetAsyncKeyState(key) & 0x8000 for key in (0x10, 0x11, 0x12, 0x5B, 0x5C))


def clipboard_text():
    user = c.WinDLL('user32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    user.GetClipboardData.argtypes = [c.c_uint]
    user.GetClipboardData.restype = c.c_void_p
    kernel.GlobalLock.argtypes = [c.c_void_p]
    kernel.GlobalLock.restype = c.c_void_p
    kernel.GlobalUnlock.argtypes = [c.c_void_p]
    if not user.OpenClipboard(None):
        raise OSError('Clipboard is busy')
    try:
        handle = user.GetClipboardData(13)
        pointer = kernel.GlobalLock(handle) if handle else None
        if not pointer:
            raise OSError('Unicode clipboard is unavailable')
        try:
            return c.wstring_at(pointer)
        finally:
            kernel.GlobalUnlock(handle)
    finally:
        user.CloseClipboard()


def send_paste(expected, guard, user=None, read_clipboard=clipboard_text, timeout=2):
    user = user or api()
    deadline = time.monotonic() + timeout
    while modifiers_down(user):
        guard.check()
        if time.monotonic() >= deadline:
            raise RuntimeError('Release Alt/Shift/Ctrl/Win and paste manually; text is in clipboard')
        time.sleep(.02)
    guard.check()
    # Clipboard ownership can change while a model is finishing.
    while True:
        try:
            actual = read_clipboard()
            break
        except OSError:
            if time.monotonic() >= deadline:
                raise RuntimeError('Clipboard is busy; paste manually when ready')
            time.sleep(.02)
    if actual != expected:
        raise RuntimeError('Clipboard changed; restore the transcript with dictate --copy-last')
    guard.check()
    if getattr(guard, 'target', None) and user.GetForegroundWindow() != guard.target[0]:
        raise RuntimeError('Foreground window changed; paste manually')
    if modifiers_down(user):
        raise RuntimeError('A modifier was pressed; paste manually')
    events = (INPUT * 4)()
    for event, key, flags in zip(events, (0x11, 0x56, 0x56, 0x11), (0, 0, 2, 2)):
        event.type = 1
        event.ki = KEYBDINPUT(key, 0, flags, 0, 0)
    count = user.SendInput(4, events, c.sizeof(INPUT))
    if count != 4:
        # Release only keys we injected, never a physically held modifier.
        cleanup = []
        if count == 2:
            cleanup.append(events[2])
        if 1 <= count < 4:
            cleanup.append(events[3])
        if cleanup:
            user.SendInput(len(cleanup), (INPUT * len(cleanup))(*cleanup), c.sizeof(INPUT))
        raise RuntimeError('Paste input was blocked or incomplete (possibly elevated target/UIPI). '
                           'Text remains in clipboard; paste manually')
