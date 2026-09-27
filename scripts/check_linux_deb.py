"""Destructive package lifecycle checks, restricted to a disposable CI container."""
import json
import os
from pathlib import Path
import subprocess
import sys


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def main():
    if os.environ.get('VTC_DISPOSABLE_CONTAINER') != '1' or not Path('/.dockerenv').exists():
        raise RuntimeError('Run only in the disposable Linux package test container')
    package = Path(sys.argv[1]).resolve()
    reports = Path(sys.argv[2]).resolve()
    reports.mkdir(parents=True, exist_ok=True)
    home = Path('/tmp/vtc-package-home')
    home.mkdir(exist_ok=True)
    os.environ.update(HOME=str(home), XDG_CONFIG_HOME=str(home / 'config'),
        XDG_DATA_HOME=str(home / 'data'), XDG_CACHE_HOME=str(home / 'cache'),
        VOICE_TO_CLIPBOARD_DATA_DIR=str(home / 'data/dictate'),
        VOICE_TO_CLIPBOARD_CACHE_DIR=str(home / 'cache'), GITHUB_ACTIONS='true',
        QT_QPA_PLATFORM='xcb', PYSTRAY_BACKEND='gtk')
    executable = Path('/opt/voice-to-clipboard/VoiceToClipboard')
    launcher = Path('/usr/share/applications/voice-to-clipboard.desktop')
    startup = home / 'config/autostart/voice-to-clipboard.desktop'
    sentinels = {
        home / 'data/dictate/settings.json': b'{"schema_version":2,"inference_device":"cuda","profiles":[{"language":"pl","key":"p","paste":false,"model":"small"}]}',
        home / 'data/dictate/history.json': b'[{"text":"private test history"}]',
        home / 'cache/huggingface/model-sentinel': b'model cache sentinel',
    }
    for path, data in sentinels.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    def preserved():
        for path, data in sentinels.items():
            assert path.read_bytes() == data, path
    run('apt-get', 'install', '-y', package)
    assert launcher.exists() and executable.exists()
    run(executable, '--install')
    assert not (home / 'data/applications/voice-to-clipboard.desktop').exists()
    run(executable, '--packaging-probe', reports / 'frozen.json', '--startup-cycle', '--cpu-inference', '--clipboard-cycle')
    entry = startup.read_bytes()
    assert b'TryExec=/opt/voice-to-clipboard/VoiceToClipboard' in entry
    preserved()
    # Upgrade to an actually higher Debian revision, using the identical runtime.
    stage = Path('/tmp/vtc-upgrade-package')
    run('dpkg-deb', '-R', package, stage)
    control = stage / 'DEBIAN/control'
    original = subprocess.check_output(['dpkg-deb', '-f', str(package), 'Version'], text=True).strip()
    upgraded = original + '+ci1'
    control.write_text(control.read_text().replace('Version: ' + original + '\n', 'Version: ' + upgraded + '\n'))
    upgrade_package = Path('/tmp/vtc-upgrade.deb')
    run('dpkg-deb', '--root-owner-group', '--build', stage, upgrade_package)
    run('apt-get', 'install', '-y', upgrade_package)
    assert subprocess.check_output(['dpkg-query', '-W', '-f=${Version}', 'voice-to-clipboard'], text=True) == upgraded
    assert startup.read_bytes() == entry
    preserved()
    run(sys.executable, '/work/scripts/check_desktop.py', '--executable', executable)
    run(executable, '--uninstall')
    assert not startup.exists()
    run('apt-get', 'remove', '-y', 'voice-to-clipboard')
    assert not executable.exists() and not launcher.exists()
    preserved()
    run('apt-get', 'install', '-y', package)
    assert not startup.exists(), 'Disabled startup changed during reinstall'
    preserved()
    # An unrelated/source startup installed later must survive frozen uninstall.
    startup.write_text('[Desktop Entry]\nExec=/source/venv/bin/voice-desktop\n')
    other = startup.read_bytes()
    run(executable, '--uninstall')
    assert startup.read_bytes() == other
    run('apt-get', 'purge', '-y', 'voice-to-clipboard')
    assert startup.read_bytes() == other
    preserved()
    (reports / 'lifecycle.json').write_text(json.dumps(dict(
        install=True, upgrade_version=upgraded, startup_enable_disable=True,
        remove_reinstall=True, purge=True, data_bytes_preserved=True,
        source_startup_preserved=True, desktop_lifecycle=True,
        physical_login=False, microphone=False), indent=2) + '\n')
    print('PASS: Linux package lifecycle, ownership and preserved settings/history/cache')


if __name__ == '__main__':
    main()
