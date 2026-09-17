"""Native Windows status window, shown without activating or restoring focus."""
import ctypes as c
from ctypes import wintypes as w
import json
import queue
import sys
import threading
import time


def window(lang):
    user = c.WinDLL('user32', use_last_error=True)
    gdi = c.WinDLL('gdi32', use_last_error=True)
    kernel = c.WinDLL('kernel32', use_last_error=True)
    callback = c.WINFUNCTYPE(c.c_ssize_t, w.HWND, w.UINT, w.WPARAM, w.LPARAM)
    class WindowClass(c.Structure):
        _fields_ = [('style', w.UINT), ('proc', callback), ('classExtra', c.c_int),
                    ('windowExtra', c.c_int), ('instance', w.HINSTANCE), ('icon', w.HANDLE),
                    ('cursor', w.HANDLE), ('background', w.HBRUSH),
                    ('menu', w.LPCWSTR), ('name', w.LPCWSTR)]
    user.DefWindowProcW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.DefWindowProcW.restype = c.c_ssize_t
    user.RegisterClassW.argtypes = [c.POINTER(WindowClass)]
    user.RegisterClassW.restype = w.ATOM
    user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                    c.c_int, c.c_int, c.c_int, c.c_int,
                                    w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
    user.CreateWindowExW.restype = w.HWND
    user.ShowWindow.argtypes = [w.HWND, c.c_int]
    user.SetWindowPos.argtypes = [w.HWND, w.HWND, c.c_int, c.c_int, c.c_int, c.c_int, w.UINT]
    user.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
    user.SendMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
    user.SendMessageW.restype = c.c_ssize_t
    user.PeekMessageW.argtypes = [c.POINTER(w.MSG), w.HWND, w.UINT, w.UINT, w.UINT]
    user.TranslateMessage.argtypes = [c.POINTER(w.MSG)]
    user.DispatchMessageW.argtypes = [c.POINTER(w.MSG)]
    user.DispatchMessageW.restype = c.c_ssize_t
    user.DestroyWindow.argtypes = [w.HWND]
    user.UnregisterClassW.argtypes = [w.LPCWSTR, w.HINSTANCE]
    kernel.GetModuleHandleW.argtypes = [w.LPCWSTR]
    kernel.GetModuleHandleW.restype = w.HINSTANCE
    gdi.CreateSolidBrush.argtypes = [w.DWORD]
    gdi.CreateSolidBrush.restype = w.HBRUSH
    gdi.SetTextColor.argtypes = [w.HDC, w.DWORD]
    gdi.SetBkColor.argtypes = [w.HDC, w.DWORD]
    gdi.GetStockObject.argtypes = [c.c_int]
    gdi.GetStockObject.restype = w.HANDLE
    gdi.DeleteObject.argtypes = [w.HANDLE]
    background = 0x2F2118  # COLORREF is BGR: #18212f.
    brush = gdi.CreateSolidBrush(background)
    @callback
    def proc(hwnd, message, wp, lp):
        if message == 0x21:  # WM_MOUSEACTIVATE
            return 3  # MA_NOACTIVATE
        if message == 0x138:  # WM_CTLCOLORSTATIC
            gdi.SetTextColor(wp, 0xFAF5F2)
            gdi.SetBkColor(wp, background)
            return brush
        return user.DefWindowProcW(hwnd, message, wp, lp)
    instance = kernel.GetModuleHandleW(None)
    name = 'VoiceToClipboardStatusOverlay'
    klass = WindowClass(proc=proc, instance=instance, background=brush, name=name)
    hwnd = None
    registered = False
    try:
        if not user.RegisterClassW(c.byref(klass)):
            raise c.WinError(c.get_last_error())
        registered = True
        width, height = 380, 145
        left = (user.GetSystemMetrics(0) - width) // 2
        # WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST, WS_POPUP.
        hwnd = user.CreateWindowExW(0x08000088, name, 'Dictate Overlay', 0x80000000,
                                    left, 40, width, height, None, None, instance, None)
        if not hwnd:
            raise c.WinError(c.get_last_error())
        def label(y, size, value):
            child = user.CreateWindowExW(0, 'STATIC', value, 0x50000000,
                                         18, y, width - 36, size, hwnd, None, instance, None)
            if not child:
                raise c.WinError(c.get_last_error())
            user.SendMessageW(child, 0x30, gdi.GetStockObject(17), 1)  # WM_SETFONT
            return child
        title = label(14, 24, 'Recording · ' + lang.upper())
        progress = label(43, 20, '')
        detail = label(70, 64, 'Press shortcut again to finish')
        updates = queue.Queue()
        def read():
            try:
                for line in sys.stdin:
                    updates.put(json.loads(line))
            finally:
                updates.put(None)
        threading.Thread(target=read, daemon=True).start()
        user.ShowWindow(hwnd, 4)  # SW_SHOWNOACTIVATE; never Tk deiconify/SetForegroundWindow.
        user.SetWindowPos(hwnd, w.HWND(-1), left, 40, width, height, 0x50)
        message = w.MSG()
        running = True
        while running:
            while user.PeekMessageW(c.byref(message), None, 0, 0, 1):
                if message.message == 0x12:
                    running = False
                    break
                user.TranslateMessage(c.byref(message))
                user.DispatchMessageW(c.byref(message))
            try:
                state = updates.get(timeout=.05)
            except queue.Empty:
                continue
            if state is None:
                break
            phase = state['state']
            heading = 'Done' if phase == 'result' else 'Transcribing' if phase == 'transcribing' else 'Recording'
            user.SetWindowTextW(title, heading + ' · ' + lang.upper())
            seconds = int(state.get('elapsed', 0))
            user.SetWindowTextW(detail, state.get('message', '') if phase == 'result' else
                               'Preparing clipboard…' if phase == 'transcribing' else
                               f'{seconds // 60:02}:{seconds % 60:02} · press shortcut again to finish')
            level = max(0, min(20, round(state.get('level', 0) * 20)))
            user.SetWindowTextW(progress, '…' if phase == 'transcribing' else '━' * level)
    finally:
        if hwnd:
            user.DestroyWindow(hwnd)
        if registered:
            user.UnregisterClassW(name, instance)
        gdi.DeleteObject(brush)
