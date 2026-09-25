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
