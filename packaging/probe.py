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
    if '--startup-cycle' in sys.argv:
        if sys.platform not in ('win32', 'darwin', 'linux') or os.environ.get('GITHUB_ACTIONS') != 'true':
            raise RuntimeError('Startup lifecycle probe is restricted to disposable CI')
        from voice_to_clipboard.platform.launchers import set_enabled, enabled
        set_enabled(True)
        assert enabled()
        set_enabled(False)
        assert not enabled()
        set_enabled(True)
        assert enabled()
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
        if sys.platform in ('win32', 'darwin') or sys.platform.startswith('linux'):
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
        atspi_checked = False
        if sys.platform.startswith('linux'):
            import subprocess
            from voice_to_clipboard.ui.desktop_app import linux_bindings
            linux_bindings()
            import pystray
            assert pystray.Icon.HAS_MENU
            probe = subprocess.run(module_command('voice_to_clipboard.platform.atspi_probe'),
                                   input='', capture_output=True, text=True, timeout=10)
            assert probe.stdout.strip(), (probe.returncode, probe.stderr)
            reply = json.loads(probe.stdout)
            assert ('ok' in reply or reply.get('error', '').startswith('Focused field not exposed')), reply
            atspi_checked = True
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
        cpu_inference = '--cpu-inference' in sys.argv
        if cpu_inference:
            import numpy as np
            from voice_to_clipboard.backends.faster_whisper import FasterModel
            model = FasterModel('tiny.en', 'auto', 'auto')
            assert model.model.model.device == 'cpu'
            segments, info = model.transcribe(np.zeros(16000, dtype=np.float32), language='en', beam_size=1)
            list(segments)  # Run the lazy native inference generator, not just model import.
            model.unload()
        clipboard_checked = '--clipboard-cycle' in sys.argv
        if clipboard_checked:
            if sys.platform != 'linux' or os.environ.get('GITHUB_ACTIONS') != 'true':
                raise RuntimeError('Clipboard probe requires disposable Linux CI')
            import subprocess
            from voice_to_clipboard.platform.desktop import to_clipboard
            sample = 'Voice to Clipboard — Україна 123'
            assert to_clipboard(sample)
            assert subprocess.check_output(['xclip', '-selection', 'clipboard', '-o']).decode('utf-8') == sample
        result = dict(clipboard_roundtrip=clipboard_checked, platform=platform.platform(), machine=platform.machine(),
                      python=platform.python_version(), frozen=bool(getattr(sys, 'frozen', False)),
                      qt_import_render_seconds=qt_ready, probe_seconds=time.perf_counter()-started,
                      portaudio=sounddevice.get_portaudio_version(),
                      ctranslate2=ctranslate2.__version__, worker_status_shutdown=True, overlay_pipe_eof=overlay_checked, atspi_dispatch=atspi_checked,
                      model_loaded=cpu_inference, cpu_synthetic_inference=cpu_inference, microphone_opened=False)
    report.write_text(json.dumps(result, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
