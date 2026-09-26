"""Destructive installer lifecycle test for a disposable Windows CI account only."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main():
    if sys.platform != 'win32' or os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('Run only on a disposable Windows GitHub Actions runner')
    import winreg
    from voice_to_clipboard.core.host_control import request
    from check_desktop import wait_ready
    setup = Path(sys.argv[1]).resolve()
    logs = Path('installer-logs').resolve()
    logs.mkdir(exist_ok=True)
    run_key = r'Software\Microsoft\Windows\CurrentVersion\Run'
    app_id = 'com.trybushenko.voicetoclipboard'
    data = Path(os.environ['LOCALAPPDATA']) / 'VoiceToClipboard'
    shortcut = Path(os.environ['APPDATA']) / 'Microsoft/Windows/Start Menu/Programs/Voice to Clipboard/Voice to Clipboard.lnk'
    # Fail closed instead of overwriting any pre-existing account data.
    assert not data.exists() and not shortcut.exists(), 'Requires a clean CI account'
    data.mkdir()
    settings = {'schema_version': 3, 'hotkey_modifiers': 'ctrl+alt+shift',
                'profiles': [{'language': 'en', 'key': 'e', 'paste': False, 'model': '', 'modifiers': 'ctrl+alt+shift'}],
                'onboarding_complete': True, 'unrelated': 'preserve'}
    (data / 'settings.json').write_text(json.dumps(settings))
    (data / 'history.json').write_text('[{"text":"installer synthetic fixture"}]')
    original = {p.name: p.read_bytes() for p in data.iterdir()}

    def preserved():
        for name, content in original.items():
            assert (data / name).read_bytes() == content, name

    def startup():
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, run_key) as key:
                return winreg.QueryValueEx(key, app_id)[0]
        except FileNotFoundError:
            return None

    assert startup() is None
    with tempfile.TemporaryDirectory(prefix='vtc installed ') as folder:
        target = Path(folder) / 'Voice to Clipboard'
        exe = target / 'VoiceToClipboard.exe'
        def install(label, success=True):
            result = subprocess.run([str(setup), '/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART',
                                     '/SP-', '/DIR=' + str(target), '/LOG=' + str(logs / (label + '.log'))], timeout=180)
            assert (result.returncode == 0) == success, (label, result.returncode)
            preserved()
        def uninstall(label):
            subprocess.run([str(target/'unins000.exe'), '/VERYSILENT', '/SUPPRESSMSGBOXES',
                            '/NORESTART', '/LOG=' + str(logs / (label + '.log'))], check=True, timeout=120)
            deadline = time.monotonic() + 20
            while exe.exists() and time.monotonic() < deadline:
                time.sleep(.1)
            assert not exe.exists() and not shortcut.exists()
            preserved()
        install('install')
        assert exe.exists() and shortcut.exists() and startup() is None
        subprocess.run([sys.executable, 'scripts/check_frozen.py', str(exe)], check=True, timeout=120)
        subprocess.run([sys.executable, 'scripts/check_desktop.py', '--executable', str(exe)], check=True, timeout=180)
        preserved()
        # Exercise the actual frozen launcher code and HKCU, not a source mock.
        subprocess.run([str(exe), '--packaging-probe', str(logs/'startup-probe.json'), '--startup-cycle'], check=True, timeout=90)
        assert str(exe) in startup()
        enabled_command = startup()
        install('upgrade-enabled')
        assert startup() == enabled_command
        # Active host blocks file replacement, including a silent installer.
        cache = Path(folder)/'cache'
        env = {**os.environ, 'VOICE_TO_CLIPBOARD_CACHE_DIR': str(cache)}
        app = subprocess.Popen([str(exe), '--run'], env=env)
        endpoint = cache/'dictate-hotkey-control.sock'
        try:
            wait_ready(endpoint, app)
            install('upgrade-running-rejected', success=False)
        finally:
            request(endpoint, 'quit')
            assert app.wait(timeout=20) == 0
        preserved()
        uninstall('uninstall-enabled')
        assert startup() is None
        install('reinstall')
        assert startup() is None
        # Reinstall reads the retained schema/profiles/history without a migration write.
        app = subprocess.Popen([str(exe), '--run'], env=env)
        try:
            state = wait_ready(endpoint, app)
            assert state['profiles'][0]['language'] == 'en'
            assert state['onboarding_complete'] is True
        finally:
            request(endpoint, 'quit')
            assert app.wait(timeout=20) == 0
        install('upgrade-disabled')
        assert startup() is None
        uninstall('uninstall-disabled')
        assert startup() is None
    Path('installer-report.json').write_text(json.dumps({
        'install_upgrade_uninstall_reinstall': True, 'retained_data_bytes': True,
        'enabled_disabled_autostart': True, 'running_upgrade_rejected': True,
        'installed_frozen_and_desktop_smoke': True,
        'real_login_microphone_cpu_dictation': 'NOT TESTED', 'signing': 'unsigned'}, indent=2))


if __name__ == '__main__':
    main()
