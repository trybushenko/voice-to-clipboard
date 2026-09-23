# Model and language compatibility

Settings offers editable model lists for the default and each profile. Empty
profile model inherits the default; an empty default uses `large-v3-turbo`.
The English explanation updates when language, override or default changes.
Use Add/Update selected, then Apply to activate and save the profile.

Known English-only models (`tiny.en`, `base.en`, `small.en`, `medium.en`,
Distil-Whisper aliases) cannot be used for another language. Older multilingual
Whisper models lack the Cantonese `yue` token; choose `large-v3` or
`large-v3-turbo` for Cantonese. Validation also runs in the host and recorder CLI
before recording/model loading. An incompatible Apply does not change saved settings.

Custom repository IDs and local paths remain editable and are marked **unverified**,
including names that merely resemble a known model. No network request or download
is made by this check. Known language support does not guarantee model availability,
backend format, hardware compatibility or transcription quality. MLX and CTranslate2
require their respective model formats; this delivery does not convert models.

Existing settings (including schema v2), overrides, modifiers and unrelated fields
are preserved. Existing incompatible pairs can still be opened in Settings for
repair; recording is blocked until corrected. Reading settings never rewrites them.
No schema bump, model replacement, cache deletion or history migration is needed.

Metadata is an explicit offline list in `core/model_compatibility.py`, based on
[faster-whisper's aliases](https://github.com/SYSTRAN/faster-whisper/blob/master/faster_whisper/utils.py),
[Distil-Whisper's English models](https://github.com/huggingface/distil-whisper), and
[Whisper's language token ordering](https://github.com/openai/whisper/blob/main/whisper/tokenizer.py).
Only exact listed identifiers are recognized; other conversions are unverified.

## Update (Windows PowerShell, from the repository)

Finish recording and quit the entire tray app before updating:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
git fetch origin
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

Linux uses `venv/bin/python` and `venv/bin/voice-hotkeys`; on Apple Silicon use
`.[mac,hotkeys,desktop]` instead of `.[whisper,hotkeys,desktop]`.

## Manual acceptance

1. In Settings select/add Polish, key P, model `distil-large-v3`. Expect an
   English-only explanation; Add/Update is rejected, existing profiles unchanged.
2. Set model `small`, Add/Update, Apply. Expect Saved and active. Quit/relaunch:
   Polish, model and shortcut modifiers remain unchanged.
3. Set override `team/custom-model`. Expect unverified warning; saving is allowed.
   Quit/relaunch preserves the exact override. Do not record with this placeholder.
4. Clear the Polish override and set default `small.en`. Apply must fail without
   changing saved settings. Set default `large-v3-turbo`, Apply: succeeds.
5. With a real compatible model, dictate a short Polish phrase. Expect Polish
   transcription in the clipboard. Real voice/download and Windows/macOS hardware
   acceptance remain separate from automated metadata/UI tests.
