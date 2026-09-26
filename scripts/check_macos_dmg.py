"""Disposable macOS CI account only: mount, copy, lifecycle, replace, remove/reinstall."""
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile


def run(*args, **kwargs):
    return subprocess.run(list(map(str, args)), check=True, timeout=180, **kwargs)


def main():
    assert sys.platform == 'darwin' and os.environ.get('CI') == 'true'
    app = Path.home() / 'Applications/VoiceToClipboard.app'
    agent = Path.home() / 'Library/LaunchAgents/com.trybushenko.voicetoclipboard.plist'
    assert not app.exists() and not agent.exists(), 'Disposable account required'
    dmg, = Path('artifacts').glob('*.dmg')
    with tempfile.TemporaryDirectory() as folder:
        mount = Path(folder) / 'mount'
        run('hdiutil', 'attach', dmg, '-nobrowse', '-mountpoint', mount)
        try:
            source = mount / app.name
            app.parent.mkdir(parents=True, exist_ok=True)
            run('ditto', source, app)
            exe = app / 'Contents/MacOS/VoiceToClipboard'
            info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
            assert info['LSMinimumSystemVersion'] == '14.0'
            assert subprocess.check_output(['lipo', '-archs', str(exe)], text=True).strip() == 'arm64'
            run(sys.executable, 'scripts/check_frozen.py', exe, '--report', 'artifacts/packaging-report.json')
            run(sys.executable, 'scripts/check_desktop.py', '--executable', exe)
            # Exercise native filesystem startup behavior using the installed executable path.
            from unittest.mock import patch
            from voice_to_clipboard.platform import launchers
            with patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'executable', str(exe)):
                launchers.set_enabled(True)
                assert launchers.enabled()
                saved = agent.read_bytes()
                # Full bundle replacement; no merge retaining obsolete libraries.
                shutil.rmtree(app)
                run('ditto', source, app)
                assert agent.read_bytes() == saved and launchers.enabled()
                launchers.set_enabled(False)
                assert not agent.exists()
                launchers.set_enabled(True)
                launchers.uninstall()
                assert not agent.exists() and app.exists()
                shutil.rmtree(app)
                run('ditto', source, app)
                assert not launchers.enabled()
            run(sys.executable, 'scripts/check_frozen.py', exe, '--report', 'artifacts/reinstall-report.json')
            Path('artifacts/lifecycle.json').write_text(json.dumps(dict(
                mount_install=True, frozen_probe=True, desktop_lifecycle=True,
                startup_file_enable_disable=True, full_bundle_replace=True,
                uninstall_reinstall=True, physical_login=False, physical_m4=False), indent=2))
        finally:
            if app.exists():
                shutil.rmtree(app)
            agent.unlink(missing_ok=True)
            run('hdiutil', 'detach', mount)


if __name__ == '__main__':
    main()
