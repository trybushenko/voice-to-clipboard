# Voice to Clipboard

Local voice dictation for writing prompts, messages and notes. Press a shortcut,
speak, press it again, and paste the transcript wherever you need it.

- Ukrainian and English shortcuts; any Whisper language via `--lang`.
- Transcribes during pauses while you continue speaking.
- Keeps Whisper warm between recordings; exits after five idle minutes.
- Optional recording/transcribing overlay.
- Local history, copy-last and append-to-last.
- No LLM rewriting, cloud transcription or automatic message sending.

## Platforms

| Platform | Speech engine | Clipboard | Overlay / shortcuts |
| --- | --- | --- | --- |
| Linux + NVIDIA | faster-whisper / CUDA | xclip (X11), wl-copy (Wayland) | GTK3; GNOME shortcuts or pynput on X11 |
| Linux / Windows without NVIDIA | faster-whisper / CPU INT8 | Native Windows Unicode clipboard on Windows | Tk on Windows; pynput |
| Windows + NVIDIA | faster-whisper / CUDA | Native Windows Unicode clipboard | Tk; pynput |
| macOS Apple Silicon, including M4 | mlx-whisper / Metal | pbcopy | Tk; pynput with system permissions |
| macOS Intel | faster-whisper / CPU INT8 | pbcopy | Tk; pynput with system permissions |

Auto-selection chooses MLX on an ARM64 Mac, CUDA when CTranslate2 detects an
NVIDIA GPU, otherwise CPU. M4 matters: use **native ARM64 Python**, not Rosetta.
MLX uses the GPU via Metal; it does not require CUDA or a separate language model.
MLX uses greedy decoding; the faster-whisper `--beam` and Silero VAD options do not
apply to MLX. Both use the recording speech gate. Accuracy/latency vary with hardware,
microphone, language and background noise.

Linux X11 recording and overlay were exercised on the development machine.
CI runs CPU-only logic/IPC tests on Linux, Windows and macOS; it does not certify
microphone permissions, physical audio devices or GUI focus on every desktop.
Windows and macOS desktop integrations should be treated as an initial port.

## Install

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
configure desktop shortcuts manually, and paste normally: pynput global hotkeys
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
remain supported by `configure-dictation.py`.

## Use

`voice-hotkeys` stays open to listen for Alt+Shift+U/E/L. Run it manually when
needed; installation does not add a login service. Stop it with Ctrl+C. A recording
already in progress remains independent: stop it with `dictate` before exiting.

You can also use the CLI (`dictate` and `voice-to-clipboard` are aliases):

```sh
dictate --lang en --overlay       # start; run dictate again to stop
dictate --lang uk --paste         # paste into the currently focused window
dictate --copy-last               # restore latest complete transcript
dictate --append                  # append another dictation to it
dictate --history                 # show history JSON
dictate --list-devices            # list microphone IDs
dictate --device 2                # select microphone; unrelated to GPU selection
dictate --silence 4               # optional stop after four seconds of silence
dictate --model small --inference-device cpu  # lighter CPU configuration
dictate --one-shot                # release model at the end of this recording
dictate --model-status            # query idle worker
dictate --unload-model            # unload idle worker now
```

The default is `large-v3-turbo`, Ukrainian, manual stop, with a 10-minute recording
limit and 20-second initial silence timeout. English shortcuts select English
explicitly. On Apple Silicon use `--backend mlx` (the automatic default), or
install the whisper extra and use `--backend faster-whisper --inference-device cpu`.
Custom MLX models accept an MLX Hugging Face repository in `--model`.
`DICTATE_MODEL`, `DICTATE_LANG`, `DICTATE_COMPUTE`, `DICTATE_PROMPT` and
`DICTATE_SILENCE`, `DICTATE_BACKEND` and `DICTATE_INFERENCE_DEVICE` can override defaults.

The overlay closes with the recording process, including on errors. It shows no
transcript. Disable with `voice-hotkeys --no-overlay` or omit `--overlay` on CLI.
Automatic paste targets the focused window when transcription finishes; normal
clipboard mode is preferable when switching chats. macOS paste uses Command+V;
Windows/Linux use Ctrl+V. Windows notifications are provided by the overlay and
console, not system toast notifications.

## Privacy and storage

Audio is held in memory, never saved by the application. Whisper weights download
from Hugging Face; speech and transcripts are not sent to a remote API.
Workers communicate through Unix sockets on Linux/macOS, or loopback TCP with a
random local authentication token on Windows. There is no externally bound server.

The latest 50 results are stored as `history.json` in:

- Linux: `$XDG_DATA_HOME/dictate` or `~/.local/share/dictate`.
- macOS: `~/Library/Application Support/VoiceToClipboard`.
- Windows: `%LOCALAPPDATA%\VoiceToClipboard`.

Override with `DICTATE_HISTORY`. Delete that file to clear history. Incomplete
transcripts are saved as incomplete and never overwrite the clipboard. On Unix
history files have mode 0600; on Windows access follows the user profile ACL.
History, recordings, environment files, model files and local backups are excluded
from Git. Existing legacy history remains readable.

## Development

```sh
python -m pip install .
python -m unittest discover -v
python test_gate.py
```

Tests do not require a microphone, model download, GUI or GPU. On Linux,
`/usr/bin/python3 check_overlay.py` shows a six-second demo and checks focus and
cleanup. `benchmark_worker.py` exercises cached Whisper weights without recording.

- `dictate.py`: recording, segmentation, history and CLI.
- `speech_backends.py`: faster-whisper and MLX adapters.
- `model_service.py`, `local_ipc.py`: persistent model and local transport.
- `platform_support.py`: clipboard, notifications, paths and process locks.
- `overlay.py`, `hotkeys.py`: optional desktop UI and keyboard host.

See [MLX Whisper](https://github.com/ml-explore/mlx-examples/tree/main/whisper)
for the Apple Silicon implementation and [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
for CPU/NVIDIA inference.
