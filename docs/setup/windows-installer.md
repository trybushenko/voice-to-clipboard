# Windows x64 CPU installer (E.2 preview)

The unsigned per-user Inno Setup installer bundles Python, Qt, PortAudio and
faster-whisper in the E.1 PyInstaller onedir layout. Git, Python and CUDA are
not prerequisites. Models are not bundled: the existing first dictation downloads
the selected model and needs network access. Windows 10/11 x64 is the intended
target; Windows Server CI is automated evidence, not clean-machine acceptance.

## Install and update

Quit Voice to Clipboard from the tray (finish dictation first). Download the
`windows-x64-cpu-installer` artifact from the **Windows CPU installer** workflow
from the [verified E.2 run](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36235750191). Extract the artifact and run the setup.
This preview is **unsigned**; Authenticode/SmartScreen trust is not established.
The SHA256 detects corruption; it is not publisher authentication.

From the extracted artifact’s `dist/installer` directory in PowerShell:

```powershell
$setup = '.\VoiceToClipboard-0.1.1-windows-x64-cpu-setup.exe'
$expected = ((Get-Content "$setup.sha256" -Raw).Trim() -split '\s+')[0]
if ((Get-FileHash $setup -Algorithm SHA256).Hash.ToLower() -ne $expected) { throw 'Checksum mismatch' }
Start-Process -FilePath $setup -Wait
```

The same command updates the existing installation. The stable app identity and
install directory retain the existing uninstall entry. Installation defaults to
`%LOCALAPPDATA%\Programs\VoiceToClipboard`. Start Menu → **Voice to Clipboard**
launches the existing tray and Settings. No new wizard or startup mechanism.
Do not run a source host and the installer app concurrently: Quit the old host
before switching distributions. Existing source commands remain supported.

Tray → **Start at login** controls the existing single HKCU Run value
`com.trybushenko.voicetoclipboard`. Installation leaves startup disabled if absent;
upgrade retains an enabled value and points it at the installed executable.
Uninstall removes that value only if it still targets this installation. A later
source-install startup value is preserved. There is no scheduled task, service,
Startup-folder shortcut, or administrator requirement.

Uninstall via Windows Settings → Apps → Voice to Clipboard. All frozen runtime
processes hold a mutex; upgrade/uninstall require Quit and never force-stop a
recording. Uninstall removes the installed files and Start Menu shortcut, keeping
`%LOCALAPPDATA%\VoiceToClipboard` (settings, profiles, history, cache) and model
caches. Reinstall uses those data. No schema migration or automatic setting rewrite
is introduced. A source launcher's same-name Start Menu shortcut is replaced by
installation; it is not restored by uninstall (re-run source `voice-desktop --install`).

In this CPU bundle `auto` means CPU even if an NVIDIA driver is present. An
existing explicit CUDA preference remains saved and yields an actionable error:
choose CPU/auto in Settings or use the source installation for CUDA. Source
`auto` selection is unchanged. GPU runtime, macOS/Linux installers and signing
are separate deliveries. Updating to future bundles may leave obsolete dependency
files until uninstall/reinstall; no broad directory deletion is used.

## Build and source update

After Quit, from a clean source checkout on Windows:

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install '.[whisper,hotkeys,desktop]'
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

For the installer build, use Python 3.12, Inno Setup 6 and the activated build venv:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r packaging/requirements.txt '.[whisper,hotkeys,desktop]'
.\packaging\windows\build.ps1
```

Outputs in `dist/installer`: versioned setup, SHA256, build-info (commit/version/
CPU/unsigned) and dependency versions. Runtime dependencies follow existing
project ranges; the build is not claimed to be bit-for-bit reproducible.
Tooling: [per-user mode](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm),
[active-process mutex](https://jrsoftware.org/ishelp/topic_setup_appmutex.htm).

## Verification and manual acceptance

Automated workflow: build installer; silent install to a path containing spaces;
installed Qt/native/worker/overlay probe; native tray/Settings/singleton and five
Quit/restart cycles; real frozen autostart enable/disable; enabled/disabled upgrade;
active-process upgrade refusal; uninstall and reinstall; retained settings/history
bytes and profile/completion reload; native tiny.en CPU inference on synthetic silence
(downloads a model; this is not a microphone/voice test). The script refuses to run outside a disposable
Windows GitHub Actions account. No real login, microphone or spoken dictation is
claimed by those checks. Same-version reinstall tests upgrade mechanics; future
cross-version acceptance remains necessary.

Manual test on a clean Windows 10/11 x64 account without Git/Python/CUDA:

1. Install, launch from Start Menu. Expect tray and existing English first-run,
   no terminal or administrator request. Finish setup with a small compatible
   model and CPU/auto; dictate a short sentence using the configured shortcut.
   Expect microphone recording, first-use model download, then clipboard text.
2. Add a second language/shortcut, enable Start at login, Quit. Install the same
   setup again. Expect profiles/history unchanged and one startup entry. Sign
   out/in: expect one tray host, working shortcut and no console. Disable startup,
   sign out/in: expect no host.
3. During recording try upgrade/uninstall. Expect a request to close the app,
   with recording preserved. Cancel setup; finish dictation and Quit.
4. Uninstall. Expect no app launcher/startup entry; data remain. Reinstall and
   launch. Expect saved profiles/history and completed first-run retained.

Record Windows version, installer checksum, CPU/model and results for the release
matrix. The user accepted the listed delivery scenarios on 2026-09-26; detailed
clean-machine/hardware coverage remains a separate release gate.

## Recorded evidence (2026-09-26)

Implementation/test head `3397697`, branch `codex/windows-cpu-installer`, based on
`origin/main` `60f8d91`. Local regression: 106 tests, 4 platform skips, passed.
[Cross-platform regression](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36235750202):
all six jobs passed. [Download installer artifact / successful lifecycle run](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36235750191):
Windows Server 2025 AMD64, Python 3.12 build; installer lifecycle, frozen native
runtime, real CPU tiny.en inference on synthetic silence passed. The earlier
lifecycle failure assumed `unins000.exe` survived rapid reinstall; the test now
reads Windows' registered UninstallString. No installer runtime change was needed
for that failure. The checks are automated evidence, not physical clean-machine,
real spoken dictation or login acceptance. Separately, on 2026-09-26 the user
confirmed the listed manual scenarios worked and authorized merge/push/branch
removal; no separate OS/model/device report was supplied. Merge `31ccd64` is on
`main`, pushed; the completed remote branch was deleted. Pre-merge review found
no blocking defects; only documentation changed after tested code `3397697`,
so tests were not rerun for acceptance/merge. Next delivery: E.3 macOS ARM64 app/DMG,
not started in this session.
