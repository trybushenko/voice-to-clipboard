# Usage and storage

For daily use, launch the desktop app from your application menu. Its tray provides
Settings, language profiles and optional Start at login. Fresh installations have
only English/E; existing U/E/L preferences are migrated. See [profiles](setup/language-profiles.md).

The optional foreground CLI `voice-hotkeys` listens for your configured profiles.
Run it manually when needed; this command alone does not enable login startup. Stop it with Ctrl+C. The host stops accepting shortcuts, requests the active
recording to finish, and waits for transcription/clipboard delivery. A second
Ctrl+C during this wait explicitly cancels its owned dictation processes. The
persistent model remains independent. If draining exceeds 15 minutes, the host
exits with a message and leaves the dictation process running.

In the dictation CLI, Ctrl+C requests recording stop and waits for the final
transcription. Further Ctrl+C presses during this drain do not discard the tail.

The running host also accepts separate control commands:

```sh
voice-hotkeys --status
voice-hotkeys --pause
voice-hotkeys --resume
voice-hotkeys --stop-recording
voice-hotkeys --quit
```

Pause unregisters shortcuts and leaves an active recording running. Resume registers
fresh shortcuts; events queued before pausing are discarded. Stop-recording only
ends recording; Quit stops the host and drains its recording. The private control
endpoint uses the same authenticated local transport as other app IPC. These are
CLI controls; equivalent actions are available from the desktop tray/menu.

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

The CLI default is `large-v3-turbo`, English, manual stop, with a 10-minute recording
limit and 20-second initial silence timeout. English shortcuts select English
explicitly. On Apple Silicon use `--backend mlx` (the automatic default), or
install the whisper extra and use `--backend faster-whisper --inference-device cpu`.
Custom MLX models accept an MLX Hugging Face repository in `--model`.
`DICTATE_MODEL`, `DICTATE_LANG`, `DICTATE_COMPUTE`, `DICTATE_PROMPT` and
`DICTATE_SILENCE`, `DICTATE_BACKEND` and `DICTATE_INFERENCE_DEVICE` can override CLI defaults. Desktop profiles explicitly select language/model; use Settings
for those rather than relying on CLI environment overrides.

The overlay closes with the recording process, including on errors. It shows no
transcript. Disable with `voice-hotkeys --no-overlay` or omit `--overlay` on CLI.
Automatic paste verifies the original destination and waits for modifier release.
Windows tracks the focused field with UI Automation; macOS uses Accessibility;
X11 observes focus and navigation input. If the target changed or verification
fails, the transcript remains in clipboard for manual paste. No caret restoration
or Enter key is attempted. The result overlay briefly shows copied, paste shortcut
sent, or manual-paste fallback. Input sent does not prove that an editor accepted it.

`voice-hotkeys --hotkey-modifiers ctrl+alt` changes and saves the modifiers for all
configured profile shortcuts after registration succeeds. Use `alt+shift` to restore defaults.
On macOS Alt means Option and the `win` modifier means Command. Prefer a combination
that does not overlap your system layout switch. Windows reports detected conflicts;
this application never changes system layout settings.

See [stage C Windows tests](setup/windows-stage-c-test.md) for focus, held-modifier,
repeat, clipboard and elevated-editor edge cases.

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


[Back to overview](../README.md)
