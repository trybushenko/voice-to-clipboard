"""Per-user desktop launchers and one reversible autostart mechanism per OS."""
import base64
import os
from pathlib import Path
import plistlib
import shlex
import shutil
import subprocess
import sys
import tempfile

APP_ID = 'com.trybushenko.voicetoclipboard'
APP_NAME = 'Voice to Clipboard'


def command():
    if getattr(sys, "frozen", False):
        from .frozen import module_command
        return module_command("voice_to_clipboard.ui.desktop_app", "--run")
    python = Path(sys.executable).absolute()
    if sys.platform == 'win32':
        candidate = python.with_name('pythonw.exe')
        if not candidate.exists():
            raise RuntimeError('pythonw.exe is missing; repair the Python/venv installation')
        python = candidate
    return [str(python), '-m', 'voice_to_clipboard.ui.desktop_app', '--run']


def _frozen_macos_app():
    app = Path(sys.executable).resolve().parent.parent.parent
    if (app.suffix != '.app' or
            app.parent not in (Path('/Applications').resolve(), (Path.home() / 'Applications').resolve())):
        raise RuntimeError('Move the app to /Applications or ~/Applications before enabling login startup')
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    if info.get('CFBundleIdentifier') != APP_ID:
        raise RuntimeError('Unexpected application bundle identifier')
    return app


def _macos_startup_arguments():
    return [str(launcher_path() / 'Contents/MacOS/VoiceToClipboard')]


def launcher_path():
    if sys.platform == 'win32':
        return Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs' / APP_NAME / (APP_NAME + '.lnk')
    if sys.platform == 'darwin':
        if getattr(sys, 'frozen', False):
            return _frozen_macos_app()
        return Path.home() / 'Applications' / (APP_NAME + '.app')
    return Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share')) / 'applications/voice-to-clipboard.desktop'


def autostart_path():
    if sys.platform == 'darwin':
        return Path.home() / 'Library/LaunchAgents' / (APP_ID + '.plist')
    return Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config')) / 'autostart/voice-to-clipboard.desktop'


def _desktop_entry():
    def quote(value):
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$').replace('%', '%%') + '"'
    return ('[Desktop Entry]\nType=Application\nName=Voice to Clipboard\n'
            'Comment=Dictate using global shortcuts\nTerminal=false\n'
            'Icon=audio-input-microphone\nCategories=Utility;Accessibility;\n'
            'Exec=' + ' '.join(quote(part) for part in command()) + '\n')


def _write(path, content, mode=0o600):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    os.close(fd)
    temporary = Path(name)
    try:
        temporary.write_bytes(content if isinstance(content, bytes) else content.encode('utf-8'))
        temporary.chmod(mode)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def install():
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin":
            return _frozen_macos_app()
        if sys.platform != "win32":
            raise RuntimeError("Frozen launcher installation is unsupported on this platform")
    path = launcher_path()
    argv = command()
    if sys.platform == 'win32':
        path.parent.mkdir(parents=True, exist_ok=True)
        def ps(value):
            return "'" + value.replace("'", "''") + "'"
        script = ("$ErrorActionPreference='Stop'; $w=New-Object -ComObject WScript.Shell; "
                  f'$s=$w.CreateShortcut({ps(str(path))}); '
                  f'$s.TargetPath={ps(argv[0])}; $s.Arguments={ps(subprocess.list2cmdline(argv[1:]))}; '
                  f'$s.WorkingDirectory={ps(str(Path(argv[0]).parent))}; $s.Save()')
        encoded = base64.b64encode(script.encode('utf-16-le')).decode('ascii')
        subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-EncodedCommand', encoded],
                       check=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW)
    elif sys.platform == 'darwin':
        if path.exists() and plistlib.loads((path / 'Contents/Info.plist').read_bytes()).get('CFBundleIdentifier') != APP_ID:
            raise RuntimeError('An app with this name already exists and is not ours')
        executable = path / 'Contents/MacOS/VoiceToClipboard'
        _write(executable, '#!/bin/sh\nexec ' + shlex.join(argv) + '\n', 0o755)
        _write(path / 'Contents/Info.plist', plistlib.dumps({
            'CFBundleIdentifier': APP_ID, 'CFBundleName': APP_NAME,
            'CFBundleDisplayName': APP_NAME, 'CFBundleExecutable': 'VoiceToClipboard',
            'CFBundlePackageType': 'APPL', 'CFBundleVersion': '1',
            'CFBundleShortVersionString': '0.1.0', 'LSUIElement': True,
            'NSMicrophoneUsageDescription': 'Record speech only when you start dictation.'}))
    else:
        _write(path, _desktop_entry(), 0o755)
    return path


def enabled():
    if sys.platform == 'win32':
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
                value, _ = winreg.QueryValueEx(key, APP_ID)
                return value == subprocess.list2cmdline(command())
        except FileNotFoundError:
            return False
    path = autostart_path()
    if not path.exists():
        return False
    if sys.platform == 'darwin':
        try:
            info = plistlib.loads(path.read_bytes())
            return (info.get('Label') == APP_ID and
                    info.get('ProgramArguments') == _macos_startup_arguments())
        except (OSError, ValueError, RuntimeError, plistlib.InvalidFileException):
            return False
    return path.read_text(encoding='utf-8') == _desktop_entry()


def set_enabled(value):
    if getattr(sys, "frozen", False) and sys.platform not in ("win32", "darwin"):
        raise RuntimeError("Frozen autostart is unsupported on this platform")
    if type(value) is not bool:
        raise ValueError('Autostart must be enabled or disabled')
    if value:
        install()
    if sys.platform == 'win32':
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r'Software\Microsoft\Windows\CurrentVersion\Run') as key:
            if value:
                winreg.SetValueEx(key, APP_ID, 0, winreg.REG_SZ, subprocess.list2cmdline(command()))
            else:
                try:
                    winreg.DeleteValue(key, APP_ID)
                except FileNotFoundError:
                    pass
    else:
        path = autostart_path()
        if value:
            if sys.platform == 'darwin':
                _write(path, plistlib.dumps({'Label': APP_ID, 'RunAtLoad': True,
                       'KeepAlive': False, 'ProcessType': 'Interactive',
                       'ProgramArguments': _macos_startup_arguments()}))
            else:
                _write(path, _desktop_entry())
        else:
            if sys.platform != "darwin" or enabled():
                path.unlink(missing_ok=True)


def uninstall():
    if sys.platform == 'darwin' and getattr(sys, 'frozen', False):
        # The running executable cannot safely delete its own loaded bundle.
        # Finder removes the app after Quit; only our matching agent is removed here.
        set_enabled(False)
        return
    set_enabled(False)
    path = launcher_path()
    if sys.platform == 'darwin' and path.exists():
        info = plistlib.loads((path / 'Contents/Info.plist').read_bytes())
        if info.get('CFBundleIdentifier') != APP_ID:
            raise RuntimeError('Refusing to remove an app with a different bundle identifier')
        shutil.rmtree(path)
    else:
        path.unlink(missing_ok=True)
    # User settings, history, venv and models are intentionally preserved.
