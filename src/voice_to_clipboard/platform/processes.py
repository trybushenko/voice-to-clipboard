"""Launch independent background processes without inheriting Ctrl+C."""
import subprocess
import sys


def spawn_background(command, no_console=False, **kwargs):
    from pathlib import Path
    command = list(command)
    if sys.platform == 'win32' and Path(command[0]).name.lower() == 'pythonw.exe':
        python = Path(command[0]).with_name('python.exe')
        if python.exists():
            command[0] = str(python)
    options = {'close_fds': True}
    if sys.platform == 'win32':
        options['creationflags'] = (subprocess.CREATE_NO_WINDOW if no_console
                                    else subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        options['start_new_session'] = True
    options.update(kwargs)
    return subprocess.Popen(command, **options)
