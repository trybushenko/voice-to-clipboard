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
| Linux + NVIDIA | faster-whisper / CUDA | xclip (X11), wl-copy (Wayland) | GTK3; GNOME shortcuts or native X11 grabs |
| Linux / Windows without NVIDIA | faster-whisper / CPU INT8 | Native Windows Unicode clipboard on Windows | Tk on Windows; RegisterHotKey |
| Windows + NVIDIA | faster-whisper / CUDA | Native Windows Unicode clipboard | Tk; RegisterHotKey |
| macOS Apple Silicon, including M4 | mlx-whisper / Metal | pbcopy | Tk; selective Quartz tap with permissions |
| macOS Intel | faster-whisper / CPU INT8 | pbcopy | Tk; selective Quartz tap with permissions |

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

## Getting started

[Installation instructions](docs/setup/installation.md) cover Linux, Windows and
macOS, including native ARM64 Python for M4 Macs.

| Shortcut | Action |
| --- | --- |
| Alt+Shift+U | Ukrainian → clipboard |
| Alt+Shift+E | English → clipboard |
| Alt+Shift+L | Ukrainian → clipboard and paste |

Press the shortcut again to stop recording. The current hotkey host must be
started manually; automatic login startup is planned. Worker, native hotkey and guarded paste changes are tracked in the roadmap;
physical desktop acceptance remains necessary on each target platform.

See [usage and private local storage](docs/usage.md) for CLI options, history,
model settings and platform limitations.

## Development

Core code is in `src/voice_to_clipboard/`, tests in `tests/`, and developer helpers
in `scripts/`. The root `dictate.py` is a compatibility wrapper for existing Linux
launchers. See [development and verification](docs/development.md).

[Desktop experience roadmap](docs/plans/desktop-experience-roadmap.md) tracks
remaining work and acceptance criteria.
