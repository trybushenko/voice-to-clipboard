"""Desktop integration and paths without importing platform-specific packages."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def data_dir():
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local')) / 'VoiceToClipboard'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/VoiceToClipboard'
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'dictate'


def cache_dir():
    if sys.platform == 'win32':
        return data_dir() / 'cache'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Caches/VoiceToClipboard'
    return Path(os.environ.get('XDG_CACHE_HOME', Path.home() / '.cache'))


class SessionLock:
    """Nonblocking process lock on Unix and Windows; released on process exit."""
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.file = open(path, 'a+b')
        try:
            if sys.platform == 'win32':
                import msvcrt
                self.file.seek(0, 2)
                if self.file.tell() == 0:
                    self.file.write(b'0')
                    self.file.flush()
                self.file.seek(0)
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.file.close()
            raise BlockingIOError('Another session owns this lock') from exc

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def notify(text, urgency='low'):
    try:
        if sys.platform == 'darwin':
            subprocess.run(['osascript', '-e', 'on run argv\ndisplay notification (item 1 of argv) with title "Voice to Clipboard"\nend run', text], timeout=3, check=False, capture_output=True)
        elif sys.platform != 'win32' and shutil.which('notify-send'):
            subprocess.run(['notify-send', '-u', urgency, '-t', '2000', '-h',
                            'string:x-canonical-private-synchronous:dictate', 'Dictate', text], timeout=3, check=False)
        # Windows uses the overlay and terminal; no modal notification dialogs.
    except (OSError, subprocess.TimeoutExpired):
        pass


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


def to_clipboard(text):
    if sys.platform == 'win32':
        return _windows_clipboard(text)
    command = ['pbcopy'] if sys.platform == 'darwin' else (
        ['wl-copy'] if os.environ.get('WAYLAND_DISPLAY') and shutil.which('wl-copy') else ['xclip', '-selection', 'clipboard'])
    if shutil.which(command[0]) is None:
        return False
    try:
        # Do not capture inherited pipes from a clipboard owner process.
        return subprocess.run(command, input=text.encode('utf-8'), timeout=5, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def do_paste():
    time.sleep(.15)
    if sys.platform == 'darwin':
        subprocess.run(['osascript', '-e', 'tell application "System Events" to keystroke "v" using command down'], timeout=5, check=True)
    elif sys.platform == 'win32':
        from pynput.keyboard import Controller, Key
        keyboard = Controller()
        with keyboard.pressed(Key.ctrl):
            keyboard.press('v')
            keyboard.release('v')
    elif shutil.which('xdotool') and not os.environ.get('WAYLAND_DISPLAY'):
        subprocess.run(['xdotool', 'key', '--clearmodifiers', 'ctrl+v'], timeout=5, check=True)
    else:
        raise RuntimeError('Automatic paste unavailable; use your normal paste shortcut')
