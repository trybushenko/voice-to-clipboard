"""Singleton Settings process; never owns a second dictation controller."""
import os
import subprocess
import sys


def open_log():
    from ..core.app_logging import log_path
    path = log_path()
    if sys.platform == 'win32':
        os.startfile(str(path))
    else:
        subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', str(path)],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    from PySide6.QtWidgets import QApplication
    from ..platform.desktop import SessionLock
    from ..platform.paths import cache_dir
    from ..core.host_control import ControlServer, request
    from .desktop_app import endpoint
    from .settings_window import SettingsWindow, style
    from functools import partial
    panel_endpoint = cache_dir() / 'dictate-panel.sock'
    try:
        lock = SessionLock(cache_dir() / 'dictate-panel.lock')
    except BlockingIOError:
        try:
            request(panel_endpoint, 'show')
        except (OSError, RuntimeError, EOFError):
            pass
        return
    control = None
    window = None
    try:
        app = QApplication.instance() or QApplication(sys.argv)
        app.setApplicationName('Voice to Clipboard')
        style(app)
        control = ControlServer(panel_endpoint)
        window = SettingsWindow(partial(request, endpoint()), control)
        window.show()
        app.exec()
    finally:
        if window:
            window.shutdown()
        if control:
            control.close()
        lock.close()


if __name__ == '__main__':
    main()
