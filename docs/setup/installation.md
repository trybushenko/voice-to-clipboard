# Install Voice to Clipboard

This is a source installation of the desktop app on `main`. You need Python and
one-time terminal commands; a standalone installer is not available yet. After setup,
launch the app from your application menu and use its tray icon without a terminal.
Use Python 3.11 or 3.12. Internet is required for package installation and the first
use of each speech model; cached models can subsequently run offline.

## 1. Download the project

Without Git: on the [repository page](https://github.com/trybushenko/voice-to-clipboard),
select **Code → Download ZIP**, extract it to a permanent folder, and open a terminal
in that folder (the one containing `pyproject.toml`). Do not run from inside the ZIP.

With Git installed:

```sh
git clone https://github.com/trybushenko/voice-to-clipboard.git
cd voice-to-clipboard
```

Keep this folder and its `.venv`: the application launcher points to that environment.
Moving it requires installing the launcher again.

## 2. Install for your platform

### Windows

Install **64-bit Python 3.12** from [Python.org](https://www.python.org/downloads/windows/),
including the Python launcher and Tcl/Tk. Open PowerShell in the project folder:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app --install
```

No environment activation or PowerShell execution-policy change is needed.
Open **Voice to Clipboard** from **Start Menu**. Its microphone icon may be inside
Windows' hidden tray icons. You can now close PowerShell.
Allow desktop apps to access your microphone in Windows privacy settings.

For a first setup without CUDA libraries, open **Settings / System check** from
the tray, select inference device **CPU**, and Apply before recording. CPU needs
no NVIDIA dependencies. GPU setup is optional; see troubleshooting below.

### macOS Apple Silicon (M1–M4)

Use native **ARM64 Python**, not Rosetta. If you use [Homebrew](https://brew.sh/):

```sh
brew install python@3.12 python-tk@3.12 portaudio ffmpeg
python3.12 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install '.[mac,hotkeys,desktop]'
.venv/bin/python -m voice_to_clipboard.ui.desktop_app --install
open "$HOME/Applications/Voice to Clipboard.app"
```

Check `.venv/bin/python -c 'import platform; print(platform.machine())'` prints
`arm64`. Apple Silicon uses MLX/Metal; CUDA is not needed.
For an Intel Mac, install `'.[whisper,hotkeys,desktop]'` instead of the `mac` extra.

Allow **Microphone**, **Accessibility**, and, if requested, **Input Monitoring**
for the application/its Python runtime in System Settings → Privacy & Security.
Restart the app after granting permissions. Alt means Option on Mac keyboards.
The launcher is an unsigned developer `.app` using your installed Python, not a
self-contained notarized release. Do not disable Gatekeeper globally.

### Linux (Ubuntu/Debian example)

Use your distribution's Python with matching GI/GTK bindings:

```sh
sudo apt update
sudo apt install python3-venv python3-pip python3-tk libportaudio2 python3-gi gir1.2-gtk-3.0 gir1.2-atspi-2.0 gir1.2-ayatanaappindicator3-0.1 xclip xdotool wl-clipboard
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
.venv/bin/python -m voice_to_clipboard.ui.desktop_app --install
.venv/bin/voice-desktop
```

Subsequent launches use **Voice to Clipboard** in your application menu.
Package names may differ on other distributions. GNOME needs tray/AppIndicator
support for a visible icon; without a tray host the app opens its control panel.
Select CPU in Settings for a first setup without NVIDIA runtime libraries.

On **X11**, the app provides native shortcuts. Do not also bind the same shortcuts
in desktop settings. Guarded paste requires an accessibility-enabled target.
On **Wayland**, use tray recording or configure desktop shortcuts to invoke the
absolute path to `.venv/bin/dictate --lang en --silence 0 --overlay`; use manual
paste. Native global shortcuts and automatic paste are not generally available.

## 3. Make your first recording

1. Open the app and put the cursor in a text editor.
2. Press **Alt+Shift+E** for English or **Alt+Shift+U** for Ukrainian.
3. Speak, then press the same shortcut again to stop. First use may take longer
   while downloading/loading the model; allow it to finish.
4. Wait for transcription to finish, then paste with **Ctrl+V** (Mac: **Cmd+V**).
5. For Ukrainian with automatic insertion, use **Alt+Shift+L**. If the original
   field cannot be verified or focus changes, text stays in clipboard for manual paste.

You can also use **Start English / Start Ukrainian → Stop recording** in the tray;
menu-started sessions copy to clipboard. **Copy last transcript** restores the last result.

In **Settings**, change shortcut modifiers if Alt+Shift conflicts with keyboard
layout switching; for example, `ctrl+alt`. The U/E/L keys and languages are currently
fixed in the desktop app. Other languages are available via CLI `--lang`; fully
configurable language profiles are planned. Application messages are in English;
errors from the OS or dependencies may use the system language.

## 4. Start automatically and exit safely

Enable **Start at login** in the tray/settings. Sign out and back in to verify it.
Disable the same option to stop automatic startup. Only one app instance should run;
launching it again opens its panel. **Pause shortcuts** disables hotkeys;
**Quit** finishes the current session before closing, with a bounded wait.
**Cancel unfinished dictation and exit** discards unfinished work.

## Troubleshooting

- **No icon:** check hidden Windows tray icons; on Linux check tray support or the
  control panel. Launch the app again to show its panel.
- **No recording:** check microphone privacy permissions and input device. Open
  **Settings / System check** for diagnostics. The model may still be downloading.
- **Shortcuts do nothing:** check Pause, OS permissions and conflicts; change
  modifiers. Do not run the legacy `voice-hotkeys` host alongside the desktop app.
- **CUDA error:** choose CPU in Settings, or install compatible CUDA/cuBLAS/cuDNN
  libraries following [faster-whisper's GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu).
  A driver alone is insufficient; the app does not automatically install GPU libraries.
- **Paste refused:** paste manually. Focus verification deliberately refuses to
  insert into an unverified field. Elevated Windows targets may also block insertion.
- **Missing Tk on macOS:** install the `python-tk` formula matching your Python.
- **More details:** use **Open log**. Share technical errors and reproduction steps,
  not private transcript history. See [storage and usage](../usage.md).

## Update or remove

Quit the app before updating. With Git, run `git pull --ff-only` on `main`; with ZIP,
update the source files. Repeat your platform's pip install and launcher install
commands above. Keep your environment at the same path.

To remove the launcher and its login startup entry, run the following with your
installed environment's Python (Windows shown):

```powershell
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app --uninstall
```

Quit the app first. On macOS/Linux use `.venv/bin/python` instead. This preserves
settings, history and cached models. Remove startup/launchers before deleting the
project folder or environment.

[Detailed desktop test guide](desktop-stage-d-test.md) · [Back to overview](../../README.md)
