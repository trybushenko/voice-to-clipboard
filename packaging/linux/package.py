"""Assemble the native onedir build as a system .deb; never visit user homes."""
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parents[2]


def main():
    version = tomllib.loads((ROOT / 'pyproject.toml').read_text())['project']['version'] + '-1'
    artifacts = ROOT / 'artifacts'
    artifacts.mkdir(exist_ok=True)
    package = artifacts / f'voice-to-clipboard_{version}_amd64.deb'
    with tempfile.TemporaryDirectory(prefix='vtc-deb-') as temporary:
        stage = Path(temporary)
        shutil.copytree(ROOT / 'dist/VoiceToClipboard', stage / 'opt/voice-to-clipboard')
        launcher = stage / 'usr/share/applications/voice-to-clipboard.desktop'
        launcher.parent.mkdir(parents=True)
        launcher.write_text('[Desktop Entry]\nType=Application\nName=Voice to Clipboard\n'
            'Comment=Local voice dictation\nExec=/opt/voice-to-clipboard/VoiceToClipboard\n'
            'TryExec=/opt/voice-to-clipboard/VoiceToClipboard\nTerminal=false\n'
            'Icon=audio-input-microphone\nCategories=Utility;Accessibility;\n')
        doc = stage / 'usr/share/doc/voice-to-clipboard'
        doc.mkdir(parents=True)
        shutil.copyfile(ROOT / 'LICENSE', doc / 'copyright')
        shutil.copyfile(ROOT / 'docs/setup/linux-deb.md', doc / 'README.md')
        control = stage / 'DEBIAN'
        control.mkdir()
        size = sum(p.stat().st_size for p in stage.rglob('*') if p.is_file()) // 1024
        (control / 'control').write_text(f'''Package: voice-to-clipboard
Version: {version}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Voice to Clipboard contributors <noreply@github.com>
Installed-Size: {size}
Depends: libc6 (>= 2.35), libstdc++6, libgcc-s1, libportaudio2, libasound2, libpulse0, libegl1, libgl1, libxcb-cursor0, libxcb-icccm4, libxcb-keysyms1, libxcb-shape0, libxkbcommon-x11-0, libgtk-3-0, libayatana-appindicator3-1, libatspi2.0-0, at-spi2-core, xclip, wl-clipboard, libnotify-bin
Suggests: gnome-shell-extension-appindicator
Homepage: https://github.com/trybushenko/voice-to-clipboard
Description: Local voice dictation with desktop controls (CPU preview)
 Bundled runtime for Ubuntu 22.04/24.04 and Pop!_OS 22.04 on amd64.
 Models download separately. User settings and history survive removal.
''')
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(package)], check=True)
    (artifacts / (package.name + '.sha256')).write_text(
        hashlib.sha256(package.read_bytes()).hexdigest() + '  ' + package.name + '\n')
    (artifacts / 'build.json').write_text(json.dumps(dict(version=version,
        commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        architecture='amd64', build_os=platform.platform(),
        targets=['Ubuntu 22.04', 'Ubuntu 24.04', 'Pop!_OS 22.04'],
        signing='unsigned preview; SHA256 is integrity only', models_included=False,
        cuda_included=False), indent=2) + '\n')


if __name__ == '__main__':
    main()
