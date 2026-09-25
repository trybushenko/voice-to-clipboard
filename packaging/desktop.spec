# Build on the target OS/architecture. No models, CUDA runtime or user data.
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all, collect_submodules

root = Path(SPECPATH).parent
hidden = collect_submodules('voice_to_clipboard')
data = [(str(root / 'packaging/probe.py'), '.')]
binaries = []
packages = ['sounddevice', 'pystray', 'faster_whisper']
if sys.platform == 'darwin':
    packages += ['mlx', 'mlx_whisper']
for package in packages:
    d, b, h = collect_all(package)
    data += d
    binaries += b
    hidden += h
# runpy dispatch cannot be discovered by static analysis.
hidden += ['PySide6.QtWidgets', 'PySide6.QtGui', 'PySide6.QtCore', 'tkinter']
a = Analysis([str(root / 'packaging/entry.py')], pathex=[str(root / 'src')],
             binaries=binaries, datas=data, hiddenimports=hidden,
             excludes=['PyQt5', 'PyQt6', 'PySide2', 'matplotlib', 'IPython', 'pytest'])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='VoiceToClipboard',
          console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='VoiceToClipboard')
if sys.platform == 'darwin':
    app = BUNDLE(coll, name='VoiceToClipboard.app',
                 bundle_identifier='com.trybushenko.voicetoclipboard',
                 info_plist={'LSUIElement': True,
                             'NSMicrophoneUsageDescription': 'Record speech only when you start dictation.'})
