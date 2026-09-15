import ctypes
import time

def _windows_clipboard(text):
    from ctypes import wintypes
    user, kernel = ctypes.WinDLL('user32', use_last_error=True), ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalLock.restype = ctypes.c_void_p
    kernel.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel.GlobalFree.argtypes = [wintypes.HGLOBAL]
    user.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user.SetClipboardData.restype = wintypes.HANDLE
    payload = (text + '\0').encode('utf-16-le')
    handle = kernel.GlobalAlloc(0x0002, len(payload))
    if not handle:
        return False
    transferred = False
    try:
        pointer = kernel.GlobalLock(handle)
        if not pointer:
            return False
        ctypes.memmove(pointer, payload, len(payload))
        kernel.GlobalUnlock(handle)
        for _ in range(10):
            if user.OpenClipboard(None):
                break
            time.sleep(.02)
        else:
            return False
        try:
            if not user.EmptyClipboard():
                return False
            transferred = bool(user.SetClipboardData(13, handle))  # CF_UNICODETEXT
            return transferred
        finally:
            user.CloseClipboard()
    finally:
        if not transferred:
            kernel.GlobalFree(handle)

