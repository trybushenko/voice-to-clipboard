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
git switch main
git pull --ff-only origin main
py -3.12 -m venv .packaging-venv
.\.packaging-venv\Scripts\python.exe -m pip install -r packaging/requirements.txt ".[whisper,hotkeys,desktop]"
.\.packaging-venv\Scripts\python.exe -m PyInstaller --clean --noconfirm packaging/desktop.spec
.\.packaging-venv\Scripts\python.exe scripts/check_frozen.py dist/VoiceToClipboard/VoiceToClipboard.exe
```

macOS ARM64, native Python 3.12:

```sh
git fetch origin
git switch main
git pull --ff-only origin main
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

For the existing Linux source installation, after Quit:

```sh
cd /home/artem-trybushenko/Projects/voice-to-clipboard
git fetch origin
git switch main
git pull --ff-only origin main
venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
venv/bin/python -m voice_to_clipboard.ui.desktop_app
```

To launch the experimental Windows bundle with disposable data (same PowerShell
window for each restart; Quit before deleting this temporary directory):

```powershell
$spikeRoot = Join-Path $env:TEMP ("vtc-spike-" + [guid]::NewGuid())
$env:VOICE_TO_CLIPBOARD_DATA_DIR = Join-Path $spikeRoot "data"
$env:VOICE_TO_CLIPBOARD_CACHE_DIR = Join-Path $spikeRoot "cache"
& .\dist\VoiceToClipboard\VoiceToClipboard.exe --run
```

On macOS use the same terminal/environment for restarts:

```sh
spike_root=$(mktemp -d /tmp/vtc-spike.XXXXXX)
export VOICE_TO_CLIPBOARD_DATA_DIR="$spike_root/data"
export VOICE_TO_CLIPBOARD_CACHE_DIR="$spike_root/cache"
dist/VoiceToClipboard.app/Contents/MacOS/VoiceToClipboard --run
```

## What the probe proves

`scripts/check_frozen.py` launches the executable from a temporary cwd without
PYTHONPATH/PYTHONHOME. The executable creates isolated data/cache/runtime paths,
imports PortAudio and the native speech backend, renders the existing Qt Settings,
spawns its own frozen worker, requests status twice, shuts it down and verifies
endpoint cleanup. Windows/macOS also exercise the real overlay stdin pipe and
clean EOF shutdown. No model loads, microphone opens or settings/history writes.
Failure or a timeout fails the workflow; a missing report is also a failure.

`bundle_bytes` counts regular files excluding symlinks (uncompressed).
`process_start_to_exit_seconds` includes bootloader, imports, Qt render, worker IPC
and shutdown, including a deliberate two-second overlay observation on Windows/macOS.
`qt_import_render_seconds` starts inside Python, after the bootloader.
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
permissions, signing and minimum OS need physical checks. CI additionally runs
`scripts/check_desktop.py --executable ...` against the real frozen host: native
tray/controller, Settings child, singleton, save/restart, pause/resume and five
Quit/restart cycles. macOS permission-denied behavior is accepted by that test;
it does not prove permitted hotkeys. Guarded paste and actual voice still need
physical end-to-end acceptance.
E.1 automation does not close E installers or F hardware/clean-machine gates.

## Short manual test

1. Run the build and probe above. Expected: exit 0, report has `frozen: true`,
   `worker_status_shutdown: true`, `overlay_pipe_eof: true`, `model_loaded: false`,
   `microphone_opened: false` on Windows/macOS.
2. With the installed app quit, launch the bundle using temporary
   `VOICE_TO_CLIPBOARD_DATA_DIR` and `VOICE_TO_CLIPBOARD_CACHE_DIR` environment values.
   Expected: tray and the existing first-run Settings, no recursive windows/processes.
3. Add a language, save and restart the same isolated bundle. Expected: profile and
   completion persist. Quit: Settings/tray and owned children close.
4. Keep original personal settings/history untouched; do not enable autostart in the
   spike. Real dictation/paste requires the separate device acceptance protocol.

## Evidence

Local source regression: 104 tests, OK, 4 platform skips. IPC suite requires local
socket access; sandbox-only failures are not counted as product failures.
Code head: `70844b7` (initial implementation `a9011f8`, frozen lifecycle `f6aaed2`).
[Final packaging CI](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009284):
both native jobs passed, including overlay pipe/EOF and frozen desktop lifecycle.
[Final regression CI](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36168009450):
all six Windows/macOS/Linux × Python 3.11/3.12 jobs passed.
Local native Linux **source** lifecycle and frozen CLI `--help` also passed.

| Measured environment | Uncompressed bytes | Imports + Qt render, seconds | Whole probe, seconds |
| --- | ---: | ---: | ---: |
| Windows Server 2025 x64, Python 3.12.10 | 376,292,084 | 0.87 | 3.81 |
| macOS 14.8.9 ARM64, Python 3.12.10 | 1,149,582,242 | 4.00 | 7.62 |
| Local Linux x64/glibc 2.35, Python 3.10.12, offscreen Qt | 551,374,792 | 0.32 | 0.92 |

Windows/macOS whole-probe times include the deliberate two-second overlay wait;
Linux does not run the overlay test. Single observations, no performance threshold
or cross-platform speed comparison. All three imported CTranslate2 4.8.2; native
CI imported PortAudio 19.7, local Linux 19.6. CI preserves the full pip inventory.
Windows Server CI is not acceptance on a clean Windows 10/11 desktop.
The macOS 14 runner is evidence for that OS only, not the deployment minimum.

Conclusion: retain PyInstaller onedir for the next installer work. Frozen child
routing, Qt, native dependencies, overlay pipe lifetime and host shutdown are
viable on both target runners. macOS bundle size (1.15 GB with MLX plus CPU
fallback dependencies), dependency locking/licenses and clean-machine behavior
remain work before release. No models or CUDA runtime were included; model
inference is not exercised by the probe. Windows user acceptance is recorded below;
merge `7ba73b2` is pushed to main; the remaining release matrix is pending.

## Windows user acceptance — 2026-09-26

The owner reports that all listed manual checks passed on a separate Windows
machine. The local report identifies Windows 11 build 26200, AMD64, bundled
Python 3.12.10, CTranslate2 4.8.2 and PortAudio 19.7. Frozen worker status/shutdown
and overlay pipe/EOF are true. Qt import/render: 4.185 s; in-process probe: 6.568 s
(includes the overlay observation). This report has no external process-start
measurement or bundle size; do not substitute the archived CI figures for them.
The Windows Server 2025 JSON also supplied by the owner is the archived CI report,
not a second measurement on the user's machine.

Accepted manual scenario: tray/Settings startup, profile save and restart,
completion persistence, singleton and Quit. The owner said all points passed;
no separate model/device/transcript record was supplied for the optional voice
check. The probe explicitly reports no model load or microphone open, so it alone
cannot establish voice/inference acceptance. This closes Windows acceptance of
the E.1 scenario, not physical Mac M4, GPU or the complete clean-machine matrix.
No code changes or repeated tests were needed for this documentation update.

## Merge — 2026-09-26

The owner reconfirmed the listed scenarios and authorized merge/push/branch deletion.
Focused review found no blocking defects; no functional code changed after the
verified `70844b7`. Existing CI and local evidence above applies; tests were not
rerun for documentation-only changes. Merge `7ba73b2` is pushed to `main` and
`origin/codex/packaging-spike` is deleted. Update/build commands now use `main`.
Next delivery: E.2 Windows per-user CPU installer, preserving settings/history
through upgrade/uninstall/reinstall and managing one login-startup entry.
No E.2 implementation was started in this session.
