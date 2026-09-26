# Voice to Clipboard

Local voice dictation for writing prompts, messages and notes. Press a shortcut,
speak, press it again, and paste the transcript wherever you need it.

- Configurable language profiles; English is the only preset for new users.
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

Windows desktop behavior has been accepted through user testing. CI checks Linux,
Windows and macOS, including native desktop lifecycle checks on Windows/macOS.
Physical Mac M4, permissions and login startup still need device-specific testing.

## Getting started

[Installation instructions](docs/setup/installation.md) cover Linux, Windows and
macOS, including native ARM64 Python for M4 Macs.

New installations start with **Alt+Shift+E → English → clipboard**. Settings opens
until setup is finished. In **Settings → Languages**, use **Add language** or
**Edit**, choose a shortcut and clipboard/paste, then **Save and finish setup**.
Later profile edits use a single **Save**. Errors keep the editor open; **Cancel**
discards its draft. Empty profile modifiers/model inherit the defaults in **Advanced**.
**General** contains overlay and login startup. Settings uses Qt/PySide6 (desktop extra).
The [Settings guide](docs/setup/settings-redesign.md) covers updates and acceptance.
Existing users see setup once after upgrading and keep their profiles during migration;
remove unwanted profiles in Settings. No Ukrainian-specific model is selected for new users.

Press the shortcut again to stop recording. Launch **Voice to Clipboard** from
Start Menu (Windows), `~/Applications` (macOS), or your Linux application menu.
Its tray/menu bar provides recording, settings, diagnostics and **Start at login**;
you do not need to keep a terminal open.

**Source installation requires Python and a one-time terminal setup.** Standalone
Windows CPU and macOS ARM64 previews are linked below. Follow the [step-by-step installation guide](docs/setup/installation.md)
for prerequisites, setup without Git, your first recording and troubleshooting.
Downloads are required for the first use of each model.
The [E.1 packaging spike](docs/setup/packaging-spike.md) provides experimental
standalone builds and verification commands; these are not release installers.

Application messages are in English; errors from the OS or dependencies may use
the system language. See [profile setup and testing](docs/setup/language-profiles.md).

See [usage and private local storage](docs/usage.md) for CLI options, history,
model settings and platform limitations.

## Development

Core code is in `src/voice_to_clipboard/`, tests in `tests/`, and developer helpers
in `scripts/`. The root `dictate.py` is a compatibility wrapper for existing Linux
launchers. See [development and verification](docs/development.md).

[Desktop experience roadmap](docs/plans/desktop-experience-roadmap.md) tracks
remaining work and acceptance criteria.

Model selection: [language compatibility, custom models and acceptance test](docs/setup/model-compatibility.md).

Windows CPU installer preview (E.2): [install/update, limitations and manual test](docs/setup/windows-installer.md).

macOS ARM64 DMG preview (E.3): [install/update, limitations and manual test](docs/setup/macos-dmg.md).
