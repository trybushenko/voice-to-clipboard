"""Visible native paste check in an isolated text field; no microphone or model.

Run with the installed virtualenv Python. --auto starts without a button click.
The synthetic test replaces clipboard content, just like dictation does.
"""
import argparse
import queue
import sys
import threading
import time
import tkinter as tk
from voice_to_clipboard.platform.desktop import to_clipboard, do_paste
from voice_to_clipboard.platform.focus import make_guard


class WindowsEdit:
    """Real Win32 EDIT fields: Tk widgets do not expose distinct UIA focus."""
    def __init__(self, parent, height):
        import ctypes as c
        from ctypes import wintypes as w
        self.c = c
        self.user = user = c.WinDLL('user32', use_last_error=True)
        user.CreateWindowExW.argtypes = [w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD,
                                        c.c_int, c.c_int, c.c_int, c.c_int,
                                        w.HWND, w.HMENU, w.HINSTANCE, c.c_void_p]
        user.CreateWindowExW.restype = w.HWND
        user.SetFocus.argtypes = [w.HWND]
        user.SetFocus.restype = w.HWND
        user.GetFocus.restype = w.HWND
        user.SetWindowTextW.argtypes = [w.HWND, w.LPCWSTR]
        user.GetWindowTextLengthW.argtypes = [w.HWND]
        user.GetWindowTextW.argtypes = [w.HWND, w.LPWSTR, c.c_int]
        self.frame = tk.Frame(parent, width=610, height=height)
        self.frame.pack(padx=12, pady=5)
        parent.update_idletasks()
        self.hwnd = user.CreateWindowExW(0, 'EDIT', '', 0x50010000 | 0x00800000 | 0x0004,
                                         0, 0, 610, height, self.frame.winfo_id(), None, None, None)
        if not self.hwnd:
            raise c.WinError(c.get_last_error())
        self.root = parent
    def focus_force(self):
        self.root.focus_force()
        self.user.SetFocus(self.hwnd)
    def has_focus(self):
        return self.user.GetFocus() == self.hwnd
    def delete(self, *args):
        self.user.SetWindowTextW(self.hwnd, '')
    def get(self, *args):
        buffer = self.c.create_unicode_buffer(self.user.GetWindowTextLengthW(self.hwnd) + 1)
        self.user.GetWindowTextW(self.hwnd, buffer, len(buffer))
        return buffer.value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--auto', action='store_true')
    parser.add_argument('--overlay', action='store_true', help='Also verify that the real overlay preserves focus')
    parser.add_argument('--change-focus', action='store_true',
                        help='Verify that switching to another field and back blocks paste')
    args = parser.parse_args()
    root = tk.Tk()
    root.title('Voice to Clipboard — paste verification')
    root.geometry('640x240')
    if sys.platform == 'win32':
        root.geometry('660x340')
        text = WindowsEdit(root, 100)
        other = WindowsEdit(root, 30) if args.change_focus else None
        focused = text.has_focus
    else:
        text = tk.Text(root, height=5)
        text.pack(fill='both', expand=True, padx=12, pady=12)
        other = tk.Entry(root)
        if args.change_focus:
            other.pack(fill='x', padx=12)
        focused = lambda: root.focus_get() == text
    changed = threading.Event()
    status = tk.StringVar(value='Press Test; keep focus in this window until the result appears.')
    tk.Label(root, textvariable=status, wraplength=610).pack(padx=12)
    results = queue.Queue()
    expected = 'Перевірка вставки — English 123.'
    running = [False]
    passed = [False]
    def worker():
        guard = make_guard()
        overlay = None
        try:
            guard.check()
            if args.overlay:
                from voice_to_clipboard.ui.overlay import Overlay
                overlay = Overlay()
                overlay.update(state='recording', elapsed=1)
                time.sleep(1)
                if overlay.process is None or overlay.process.poll() is not None:
                    raise RuntimeError('Overlay failed to start')
                overlay.update(state='transcribing', elapsed=1)
                time.sleep(.3)
                guard.check()
            if args.change_focus:
                results.put(('change-focus', None))
                if not changed.wait(5):
                    raise RuntimeError('Test did not complete its focus switch')
            if not to_clipboard(expected):
                raise RuntimeError('Clipboard write failed')
            try:
                do_paste(expected, guard)
            except RuntimeError as exc:
                if args.change_focus:
                    results.put(('blocked', str(exc)))
                    return
                raise
            results.put(None)
        except Exception as exc:
            results.put(str(exc))
        finally:
            if overlay is not None:
                overlay.close()
            guard.close()
    def start():
        if running[0]:
            return
        running[0] = True
        changed.clear()
        text.delete('1.0', 'end')
        text.focus_force()
        status.set('Checking field identity and native paste…')
        root.after(300, lambda: threading.Thread(target=worker, daemon=True).start())
    def finish(error):
        actual = text.get('1.0', 'end-1c')
        if args.change_focus:
            passed[0] = isinstance(error, tuple) and error[0] == 'blocked' and not actual and not other.get()
            result = 'PASS: switching fields and returning blocked paste.' if passed[0] else f'FAIL: expected blocked paste; {error!r}'
        else:
            passed[0] = error is None and actual == expected and focused()
            result = 'PASS: exact Unicode text inserted once; focus preserved.' if passed[0] else 'FAIL: ' + (error or 'Text did not appear exactly once in the original field')
        status.set(result)
        print(result, flush=True)
        running[0] = False
        if args.auto:
            root.after(300, root.destroy)
    def poll():
        try:
            result = results.get_nowait()
            if isinstance(result, tuple) and result[0] == 'change-focus':
                other.focus_force()
                root.after(250, text.focus_force)
                root.after(500, changed.set)
            else:
                # Input injection and the target's paste handler are asynchronous.
                root.after(500, lambda: finish(result))
        except queue.Empty:
            pass
        root.after(50, poll)
    tk.Button(root, text='Test native paste', command=start).pack(pady=10)
    if args.auto:
        root.after(500, start)
    root.after(50, poll)
    root.mainloop()
    if args.auto and not passed[0]:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
