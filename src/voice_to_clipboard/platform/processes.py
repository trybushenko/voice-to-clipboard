"""Launch independent background processes without inheriting Ctrl+C."""
import subprocess
import sys


def spawn_background(command, no_console=False, **kwargs):
    options = {'close_fds': True}
    if sys.platform == 'win32':
        options['creationflags'] = (subprocess.CREATE_NO_WINDOW if no_console
                                    else subprocess.CREATE_NEW_PROCESS_GROUP)
    else:
        options['start_new_session'] = True
    options.update(kwargs)
    return subprocess.Popen(command, **options)
