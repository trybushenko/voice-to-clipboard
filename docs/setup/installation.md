# Installation

Clone and use Python 3.11 or 3.12 (minimum 3.10). Models download on first use;
subsequent transcription can run offline with cached models.

```sh
git clone https://github.com/trybushenko/voice-to-clipboard.git
cd voice-to-clipboard
```

### macOS M4 / M1–M3

Install native ARM64 Python. For Homebrew Python:

```sh
brew install python@3.12 python-tk@3.12 portaudio ffmpeg
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install '.[mac,hotkeys]'
voice-hotkeys
```

Allow **Microphone**, **Accessibility**, and (if requested) **Input Monitoring**
for your terminal/Python in System Settings → Privacy & Security. Restart the
hotkey process after granting permissions. On a Mac, Alt means Option.
If the overlay reports a missing Tk installation, install the matching python-tk
formula, or run `voice-hotkeys --no-overlay`.

For an Intel Mac, install `'.[whisper,hotkeys]'` instead.

### Windows

Use a 64-bit Python installation with Tcl/Tk (the python.org installer includes it).
In PowerShell, no activation or execution-policy change is required:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys]"
.\.venv\Scripts\voice-hotkeys.exe
```

Allow desktop apps to access your microphone in Windows Settings. CPU works
without NVIDIA libraries. To use NVIDIA acceleration, install compatible CUDA 12
cuBLAS and cuDNN 9 libraries and put their DLL directories on PATH; see
[faster-whisper GPU requirements](https://github.com/SYSTRAN/faster-whisper#gpu).
If an installed NVIDIA driver is detected but CUDA libraries are missing, use
`voice-hotkeys --inference-device cpu` (or the same flag on `dictate`) or install the libraries. CUDA errors are surfaced,
not silently hidden behind CPU fallback.

### Linux

Ubuntu/Pop!_OS example:

```sh
sudo apt install libportaudio2 xclip xdotool python3-gi gir1.2-gtk-3.0
python3 -m venv .venv
source .venv/bin/activate
python -m pip install '.[whisper,hotkeys]'
voice-hotkeys
```

For NVIDIA, install the CUDA libraries above. On Wayland, install `wl-clipboard`,
configure desktop shortcuts manually, and paste normally: the native hotkey host
and automatic paste are not generally available under Wayland.
GTK overlay uses `/usr/bin/python3`; the core application uses your virtualenv.

GNOME users can instead bind these commands in Settings → Keyboard:

| Shortcut | Command |
| --- | --- |
| Alt+Shift+U | `dictate --lang uk --silence 0 --overlay` |
| Alt+Shift+E | `dictate --lang en --beam 5 --silence 0 --overlay` |
| Alt+Shift+L | `dictate --lang uk --silence 0 --paste --overlay` |

Use the **absolute path** to the `dictate` executable in your virtualenv if the
desktop does not inherit its PATH. Do not run `voice-hotkeys` alongside desktop
bindings for the same shortcuts. Existing development-machine GNOME bindings
remain supported by `scripts/configure-dictation.py`.


[Back to overview](../../README.md)

### Console-independent hotkeys (B/C testing branch)

After installation, run `voice-hotkeys --background` once. The command returns;
closing that terminal does not close the background host. Use `--status`, `--pause`,
`--resume`, `--stop-recording`, `--quit` to control it. This is not login autostart.
The host's diagnostic log is `logs/hotkeys.log` under the application data directory;
recording-child output is discarded in background mode. Use foreground for diagnostics.

X11 guarded paste additionally needs system Python GI/AT-SPI bindings (Debian/Ubuntu:
`python3-gi gir1.2-atspi-2.0`) and an accessibility-enabled target application.
Unavailable field identity safely leaves text in the clipboard. Wayland uses the
existing desktop-shortcut/manual-paste workflow. The Tk paste-check script is intended
for Windows/macOS; Linux Tk may not expose AT-SPI field identity.
