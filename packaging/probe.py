"""Frozen native-import/Qt/worker probe. No downloads, microphone or real settings."""
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time


def main():
    report = Path(sys.argv[1]).resolve()
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix='vtc-freeze-') as folder:
        os.environ.update(VOICE_TO_CLIPBOARD_DATA_DIR=folder,
                          VOICE_TO_CLIPBOARD_CACHE_DIR=folder, DICTATE_RUNTIME=folder)
        from voice_to_clipboard.platform.frozen import module_command
        from voice_to_clipboard.platform.processes import spawn_background
        from voice_to_clipboard.worker.transport import connect
        from voice_to_clipboard.worker.protocol import send, receive
        import sounddevice
        import faster_whisper
        import ctranslate2
        if sys.platform == 'darwin':
            import mlx.core
            import mlx_whisper
        from PySide6.QtWidgets import QApplication
        from voice_to_clipboard.ui.settings_window import SettingsWindow, style
        app = QApplication([])
        style(app)
        window = SettingsWindow(lambda *args, **kwargs: {'state': 'listening'})
        window.show()
        app.processEvents()
        assert window.isVisible()
        window.shutdown()
        window.hide()
        qt_ready = time.perf_counter() - started
        overlay_checked = False
        if sys.platform in ('win32', 'darwin'):
            from voice_to_clipboard.ui.overlay import Overlay
            overlay = Overlay(lang='en')
            try:
                assert overlay.process is not None
                overlay.update(elapsed=1, level=.1)
                time.sleep(2)
                assert overlay.process.poll() is None, 'Frozen overlay exited before EOF'
                # EOF must close the actual native window, not merely kill the process.
                overlay._enqueue(None)
                assert overlay.process.wait(timeout=8) == 0
                overlay_checked = True
            finally:
                overlay.close()
        child = spawn_background(module_command('voice_to_clipboard.worker.service'), no_console=True)
        path = Path(folder) / 'worker.sock'
        def request(op):
            with connect(path, timeout=1) as connection:
                send(connection, {'op': op})
                return receive(connection)
        try:
            deadline = time.monotonic() + 30
            while True:
                try:
                    status = request('status')
                    break
                except (OSError, ValueError):
                    if child.poll() is not None or time.monotonic() >= deadline:
                        raise RuntimeError('Frozen worker did not become ready')
                    time.sleep(.05)
            assert status == {'loaded': False, 'config': None}, status
            assert request('status') == status  # Same process, second IPC connection.
            assert request('shutdown') == {'ok': True}
            assert child.wait(timeout=10) == 0
            assert not path.exists()
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=10)
        assert not (Path(folder) / 'settings.json').exists()
        assert not (Path(folder) / 'history.json').exists()
        result = dict(platform=platform.platform(), machine=platform.machine(),
                      python=platform.python_version(), frozen=bool(getattr(sys, 'frozen', False)),
                      qt_import_render_seconds=qt_ready, probe_seconds=time.perf_counter()-started,
                      portaudio=sounddevice.get_portaudio_version(),
                      ctranslate2=ctranslate2.__version__, worker_status_shutdown=True, overlay_pipe_eof=overlay_checked,
                      model_loaded=False, microphone_opened=False)
    report.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
