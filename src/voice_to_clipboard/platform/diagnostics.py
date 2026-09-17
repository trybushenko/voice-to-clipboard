"""Read-only baseline system check; never records audio or downloads a model."""
import importlib.util
import platform
import shutil
import sys
import tempfile
from .paths import data_dir


def report():
    lines = [f'OS: {platform.system()} {platform.release()} ({platform.machine()})',
             f'Python: {sys.version.split()[0]}', f'Runtime: {sys.executable}']
    for module in ('sounddevice', 'pystray', 'PIL', 'pynput'):
        lines.append(f'{module}: ' + ('available' if importlib.util.find_spec(module) else 'MISSING — reinstall .[desktop,hotkeys]'))
    backend = 'mlx_whisper' if sys.platform == 'darwin' and platform.machine() == 'arm64' else 'faster_whisper'
    lines.append(f'Speech backend {backend}: ' + ('available' if importlib.util.find_spec(backend) else 'MISSING — install mac/whisper extra'))
    try:
        import sounddevice as sd
        devices = [device for device in sd.query_devices() if device['max_input_channels'] > 0]
        lines.append(f'Microphone input devices: {len(devices)}' + ('' if devices else ' — connect a microphone and check OS permissions'))
    except Exception as exc:
        lines.append(f'Microphone check failed ({type(exc).__name__}); check audio drivers and microphone permission')
    try:
        path = data_dir()
        path.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(dir=path):
            pass
        lines.append(f'Data directory writable; free disk: {shutil.disk_usage(path).free // (1024**3)} GiB')
    except OSError:
        lines.append('Data directory is not writable — check user permissions and disk space')
    if sys.platform == 'win32':
        from .windows_hotkeys import layout_conflict
        from ..core.settings import read_modifiers
        lines.append('Layout-switch conflict: ' + ('YES — choose Ctrl+Alt in Settings' if layout_conflict(read_modifiers()) else 'not detected'))
        lines.append('If recording fails: Windows Settings → Privacy → Microphone → allow desktop apps.')
    elif sys.platform == 'darwin':
        try:
            from ApplicationServices import AXIsProcessTrusted
            lines.append('Accessibility: ' + ('allowed' if AXIsProcessTrusted() else 'allow this app/Python in System Settings → Privacy & Security'))
        except ImportError:
            lines.append('Accessibility bindings missing — install hotkeys extra')
        lines.append('Also check Microphone and Input Monitoring in Privacy & Security.')
    else:
        import os
        lines.append('Session: ' + ('Wayland — desktop bindings/manual paste' if os.environ.get('WAYLAND_DISPLAY') else 'X11'))
        for program in ('xclip', 'wl-copy'):
            lines.append(program + ': ' + ('available' if shutil.which(program) else 'not installed'))
    lines.append('This check does not open the microphone or run GPU inference; runtime/backend verification belongs to setup stage E.')
    return '\n'.join(lines)
