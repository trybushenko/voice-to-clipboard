"""Explicit routing for subprocesses in the standalone desktop executable."""
import runpy
import sys

MODULES = frozenset({
    'voice_to_clipboard', 'voice_to_clipboard.ui.desktop_app',
    'voice_to_clipboard.ui.desktop_panel', 'voice_to_clipboard.ui.hotkeys',
    'voice_to_clipboard.ui.overlay', 'voice_to_clipboard.worker.service',
})


def module_command(module, *arguments):
    if module not in MODULES:
        raise ValueError('Unsupported application module: ' + module)
    flag = '--app-module' if getattr(sys, 'frozen', False) else '-m'
    return [sys.executable, flag, module, *arguments]


def dispatch(arguments):
    args = list(arguments)
    module = 'voice_to_clipboard.ui.desktop_app'
    if args[:1] == ['--app-module']:
        if len(args) < 2 or args[1] not in MODULES:
            raise ValueError('Unsupported application module')
        module, args = args[1], args[2:]
    sys.argv = [sys.executable, *args]
    runpy.run_module(module, run_name='__main__')


def restore_standard_streams():
    """Windowed Windows Python drops streams, even when the parent supplies pipes."""
    import os
    for name, number in (('stdin', -10), ('stdout', -11), ('stderr', -12)):
        if getattr(sys, name) is not None:
            continue
        mode = 'r' if name == 'stdin' else 'w'
        stream = None
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            import msvcrt
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel.GetStdHandle.argtypes = [wintypes.DWORD]
            kernel.GetStdHandle.restype = wintypes.HANDLE
            kernel.GetCurrentProcess.restype = wintypes.HANDLE
            kernel.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                wintypes.HANDLE, ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                wintypes.BOOL, wintypes.DWORD]
            kernel.DuplicateHandle.restype = wintypes.BOOL
            kernel.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = kernel.GetStdHandle(number)
            current = kernel.GetCurrentProcess()
            duplicate = wintypes.HANDLE()
            if handle and handle != wintypes.HANDLE(-1).value and kernel.DuplicateHandle(
                    current, handle, current, ctypes.byref(duplicate), 0, False, 2):
                try:
                    fd = msvcrt.open_osfhandle(duplicate.value,
                        (os.O_RDONLY if mode == 'r' else os.O_WRONLY) | os.O_BINARY)
                except OSError:
                    kernel.CloseHandle(duplicate)
                else:
                    stream = os.fdopen(fd, mode, encoding='utf-8', buffering=1)
        setattr(sys, name, stream if stream is not None else open(os.devnull, mode))


# Kept open until process exit, including worker/panel/overlay children. Inno
# checks this mutex before upgrade/uninstall and never force-kills dictation.
_install_mutex = None


def hold_install_mutex():
    global _install_mutex
    if sys.platform != 'win32' or _install_mutex is not None:
        return
    import ctypes
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    _install_mutex = kernel.CreateMutexW(None, False, 'Local\\VoiceToClipboard.Desktop.Runtime')
    if not _install_mutex:
        raise ctypes.WinError(ctypes.get_last_error())
