# E.1 — standalone packaging spike

Branch `codex/packaging-spike`, based on `origin/main` `27add90`.
This is a developer experiment, not an installer or a release. No settings schema,
profile defaults, model selection, history paths or source-install behavior changes.

## Decision and scope

Use **PyInstaller 6.22.0, onedir**, building separately on Windows x64 and macOS
ARM64 with Python 3.12. The spec includes existing Qt Settings, tray, native helpers,
PortAudio and speech dependencies; models and NVIDIA runtime are not bundled.
The application dispatches explicit child roles instead of asking its frozen
executable to interpret `-m`. Source Python commands retain their original form.

| Candidate | Assessment for this spike |
| --- | --- |
| PyInstaller onedir | Selected candidate: inspectable dependency tree, direct Python hooks, no per-launch onefile extraction; measured by the committed workflow. |
| PyInstaller onefile | Deferred: extraction complicates startup and child-process lifetime; no measured comparison claimed. |
| Qt pyside6-deploy / Nuitka | Qt-supported alternative, requires a compilation toolchain and a separate native dependency investigation; not benchmarked here. |

References: [PyInstaller deployment pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
and [Qt pyside6-deploy](https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html).
This is an engineering selection, not a claim that another bundler is slower.

## Reproduce

After Quit, from the repository (developer path; Python/Git required):

```powershell
git fetch origin
git switch codex/packaging-spike
git pull --ff-only origin codex/packaging-spike
py -3.12 -m venv .packaging-venv
.\.packaging-venv\Scripts\python.exe -m pip install -r packaging/requirements.txt ".[whisper,hotkeys,desktop]"
.\.packaging-venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging/desktop.spec
.\.packaging-venv\Scripts\python.exe scripts/check_frozen.py dist/VoiceToClipboard/VoiceToClipboard.exe
```

macOS ARM64, native Python 3.12:

```sh
git fetch origin
git switch codex/packaging-spike
git pull --ff-only origin codex/packaging-spike
python3.12 -m venv .packaging-venv
.packaging-venv/bin/python -m pip install -r packaging/requirements.txt '.[mac,whisper,hotkeys,desktop]'
.packaging-venv/bin/python -m PyInstaller --clean --noconfirm packaging/desktop.spec
.packaging-venv/bin/python scripts/check_frozen.py dist/VoiceToClipboard.app/Contents/MacOS/VoiceToClipboard
```

CI preserves dependency versions, build warnings, report and tar archive for seven
days. Preserve symlinks when extracting/copying the macOS bundle. There is no
Release upload, signing identity, notarization, updater, DMG or Windows installer.
Autostart/install/uninstall mutations in this experimental bundle fail explicitly;
source installations keep their existing launcher behavior. Do not replace the
installed app with this temporary build.

## What the probe proves

`scripts/check_frozen.py` launches the executable from a temporary cwd without
PYTHONPATH/PYTHONHOME. The executable creates isolated data/cache/runtime paths,
imports PortAudio and the native speech backend, renders the existing Qt Settings,
spawns its own frozen worker, requests status twice, shuts it down and verifies
endpoint cleanup. No model loads, microphone opens or settings/history writes.
Failure or a timeout fails the workflow; a missing report is also a failure.

`bundle_bytes` counts regular files excluding symlinks (uncompressed).
`process_start_to_exit_seconds` includes bootloader, imports, Qt render, worker IPC
and shutdown. `qt_import_render_seconds` starts inside Python, after the bootloader.
These are fresh-process timings with uncontrolled OS caches, **not** reboot-cold
startup or time to usable dictation. Runtime dependency versions are captured in
`packaging-dependencies.txt`; runtime dependencies are not yet fully locked.

## Support matrix and release gates

| Target | Intended backend | Scope |
| --- | --- | --- |
| Windows x64, CPU | faster-whisper / INT8 | Native CI bundle + probe; physical mic/inference and clean machine still required. |
| macOS ARM64 | MLX / Metal, faster-whisper CPU available | Native ARM64 CI bundle + probe; M4, permissions, deployment minimum and real Metal inference still required. |
| Linux x64 | faster-whisper | Auxiliary local build probe only; GTK/AT-SPI/system dependencies and package format remain open. |
| Windows NVIDIA / macOS Intel / other Linux | Existing source support only | No standalone packaging acceptance in E.1. |

PortAudio import does not prove microphone permissions. Native backend import does
not prove model download/inference. GTK/AT-SPI external helpers and frozen library
search-path interactions still need Linux packaging work. macOS Tk overlay,
permissions, signing and minimum OS need physical checks. Frozen tray/hotkeys,
overlay, guarded paste and first-run/restart need end-to-end desktop acceptance.
E.1 automation does not close E installers or F hardware/clean-machine gates.

## Short manual test

1. Run the build and probe above. Expected: exit 0, report has `frozen: true`,
   `worker_status_shutdown: true`, `model_loaded: false`, `microphone_opened: false`.
2. With the installed app quit, launch the bundle using temporary
   `VOICE_TO_CLIPBOARD_DATA_DIR` and `VOICE_TO_CLIPBOARD_CACHE_DIR` environment values.
   Expected: tray and the existing first-run Settings, no recursive windows/processes.
3. Add a language, save and restart the same isolated bundle. Expected: profile and
   completion persist. Quit: Settings/tray and owned children close.
4. Keep original personal settings/history untouched; do not enable autostart in the
   spike. Real dictation/paste requires the separate device acceptance protocol.

## Evidence

Local source regression: 103 tests, OK, 4 platform skips. IPC suite requires local
socket access; sandbox-only failures are not counted as product failures.
Frozen build/CI measurements are recorded below after execution.
