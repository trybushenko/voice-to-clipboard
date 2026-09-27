# Linux CPU .deb preview (E.4)

Target: Ubuntu 22.04/24.04 and Pop!_OS 22.04, **amd64**, glibc 2.35 or newer.
The package bundles Python, GTK/GI, Qt and faster-whisper; Git, Python development
tools and CUDA are not installation prerequisites. APT supplies desktop/audio
libraries and clipboard tools. Models download on first use. `auto` uses CPU;
explicit CUDA settings are preserved and produce an actionable error. Existing
source installs keep their CUDA behavior and existing configuration paths.

## Install or update

Download and extract artifact `linux-amd64-deb` from the **Linux CPU deb** workflow
for `codex/linux-deb-package`. It contains an unsigned `.deb`, SHA256, dependency
list, build metadata and test reports. Artifacts expire after 14 days; rebuild
with workflow_dispatch if needed. This is a preview, not a signed APT repository.

Finish dictation and **Quit** the entire old app before updating. Close Settings
alone does not stop it. There is no running-update blocker or automatic updater.
From the directory containing the extracted files:

```sh
sha256sum -c voice-to-clipboard_0.1.1-1_amd64.deb.sha256
sudo apt update
sudo apt install ./voice-to-clipboard_0.1.1-1_amd64.deb
/opt/voice-to-clipboard/VoiceToClipboard
```

Subsequently launch **Voice to Clipboard** from the application menu. Enable
**Start at login** in General or the tray. It uses the existing single
`~/.config/autostart/voice-to-clipboard.desktop` (or XDG_CONFIG_HOME), never a
second service. Update preserves that entry. Disabling removes it only when
it matches this runtime. GNOME needs its AppIndicator extension enabled for a
persistent tray; absent a tray host, the existing Settings fallback applies.

When migrating from source, Quit first and run the source environment's
`python -m voice_to_clipboard.ui.desktop_app --uninstall` before installing the
.deb. This removes its user launcher (which otherwise shadows the system one)
and its matching startup, preserving all data. Enable package startup afterwards.
Existing desktop custom shortcuts are not rewritten; keep the source environment
if they still point to it, or explicitly change them to the frozen CLI below.

## Remove / reinstall

As your normal desktop user, disable **Start at login** and Quit. Alternatively,
after Quit, remove this user's matching autostart via the installed executable:

```sh
/opt/voice-to-clipboard/VoiceToClipboard --uninstall
sudo apt remove voice-to-clipboard
```

The first command only removes this runtime's matching per-user startup; dpkg
owns the system launcher/runtime. APT never scans or writes other users' homes.
On shared machines each user should disable their startup before removal. APT
removal alone leaves any per-user entry inert (`TryExec`); it becomes active
again after reinstall. `apt purge` also preserves personal data. Reinstall using
the install command above; profiles, settings, history and model cache remain.
Source startup installed later is not removed by the frozen uninstall command.

## X11 / Wayland

X11 uses existing native hotkeys and guarded paste. AT-SPI must expose the target
field; uncertainty falls back to clipboard. Wayland retains desktop custom
bindings and manual paste, with no portal/global-hotkey or automatic-paste claim.
For a Wayland desktop shortcut, use the existing CLI through the frozen dispatcher:

```sh
/opt/voice-to-clipboard/VoiceToClipboard --app-module voice_to_clipboard --lang en
```

Keep the existing CLI stop/toggle behavior documented in [usage](../usage.md).
This packaging change adds no new workflow or shortcut registration mechanism.

## Build and automated verification

Build on Ubuntu 22.04 (or Pop!_OS 22.04), using distro Python 3.10 plus matching GI:

```sh
sudo apt install build-essential python3-venv python3-dev python3-tk python3-gi python3-gi-cairo libglib2.0-bin libharfbuzz-gobject0 gir1.2-gtk-3.0 gir1.2-atspi-2.0 gir1.2-ayatanaappindicator3-0.1 libportaudio2 libegl1 libgl1 libxcb-cursor0 libxcb-icccm4 libxcb-keysyms1 libxcb-shape0 libxkbcommon-x11-0 dpkg-dev
python3 -m venv --system-site-packages .packaging-venv
.packaging-venv/bin/python -m pip install --upgrade pip setuptools wheel
.packaging-venv/bin/python -m pip install -r packaging/requirements.txt '.[whisper,hotkeys,desktop]'
PATH="$PWD/.packaging-venv/bin:$PATH" bash packaging/linux/build.sh
```

The workflow installs the result in clean Ubuntu 22.04/24.04 containers, with a
disposable HOME, Xvfb and D-Bus: package lifecycle/data preservation, startup
ownership, frozen Qt/GTK/overlay/worker, native desktop lifecycle and CPU synthetic
inference. These checks do not prove microphone capture, real speech accuracy,
physical login, a compositor's tray or Wayland behavior. See the roadmap for
actual results and unperformed acceptance checks.

## Short manual acceptance

1. Quit old app, install and launch. Expect tray/Settings without a terminal or
   developer setup; existing profiles remain, or English first-run on a new user.
2. Choose CPU/auto and a small model, finish setup. Dictate a short phrase on X11,
   stop with the same shortcut, paste into an editor. Expect one transcript in
   clipboard and no stray shortcut letter. On Wayland use your desktop binding
   and manual paste; do not expect native hotkeys or guarded automatic paste.
3. Enable login startup; log out/in. Expect one app. Disable and repeat: no app.
4. Save a profile, Quit, reinstall the .deb; expect the same profile/history.
   Disable startup → Quit → uninstall → APT remove: launcher gone, data intact.
   Reinstall: data restored. Quit must close microphone, host and owned children.

Record OS/session, model/device and actual results. Physical Pop!_OS/Ubuntu voice,
login and Wayland acceptance remain separate from automated container checks.

System clipboard/notification/portal commands receive the original system library
path, following [PyInstaller external-program guidance](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application).
Frozen app children retain the bundled libraries.
