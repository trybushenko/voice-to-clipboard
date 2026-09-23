# First-run setup in Settings

The existing Settings panel opens until **Finish setup and apply** succeeds.
This also happens once after upgrading an existing installation without a
completion flag. Existing profiles, model overrides, modifiers and history remain
unchanged until Apply. A clean installation remembers only its English/E preset
at startup, without marking setup complete; recording before Finish must not
accidentally trigger legacy U/E/L migration on the next launch.

1. Select a profile to edit, or choose a language and **Add** a new profile.
2. Choose an A–Z key and optional profile modifiers (empty inherits the default).
   Leave **Paste with hotkey** unchecked for clipboard only. Paste uses the
   original field only when it can be verified; otherwise paste manually.
3. Keep the multilingual default or choose a compatible model. After editing an
   existing profile click **Update selected**. Review the listed profiles.
4. Click **Finish setup and apply**, then wait for **Saved and active. Setup
   complete.** Shortcuts and completion are saved in the same transaction.

Closing before Finish leaves setup incomplete; reopen Settings from the tray or
restart the app to resume from saved profiles. Unsaved edits are not restored.
Validation, shortcut registration or persistence failure keeps setup incomplete
and retains the previously saved preferences. After completion, the button
returns to **Apply all settings and profiles**; Settings stays available from the
tray. On Linux without an embedded GTK tray, the control panel still opens as an
accessibility fallback even after setup is complete.

This is configuration only: no microphone test, download, inference or permission
grant runs during Finish. Model compatibility is an offline check; custom models
remain unverified. Schema v2/v3 reads and unknown settings fields are preserved;
the optional boolean `onboarding_complete` does not require a schema bump.

## Update this delivery

Windows PowerShell, in the repository, after finishing any recording. Quit the
whole tray app and wait for its icon to disappear before installing:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
git fetch origin
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

Linux equivalent (source installation with `venv`):

```sh
venv/bin/voice-hotkeys --quit
git fetch origin
git switch main
git pull --ff-only origin main
venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
venv/bin/python -m voice_to_clipboard.ui.desktop_app
```

On Apple Silicon use your native ARM64 Python environment and
`.[mac,hotkeys,desktop]`. This delivery is accepted and merged into main (`1a6e23c`, implementation `8f192b1`).

## Short manual acceptance

For a clean test without touching personal settings/history, quit the app first,
then in a separate PowerShell window set isolated paths before launching:

```powershell
$vtcSetupTest = Join-Path $env:TEMP ("vtc-setup-" + [guid]::NewGuid())
$env:VOICE_TO_CLIPBOARD_DATA_DIR = Join-Path $vtcSetupTest 'data'
$env:VOICE_TO_CLIPBOARD_CACHE_DIR = Join-Path $vtcSetupTest 'cache'
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

1. Expect Welcome and English/E only. Close Settings, Quit the tray app, relaunch
   in the same shell: Welcome appears again with English only.
2. Select English; change to Polish/P, choose clipboard or paste and `small`;
   click Update selected. Set default modifiers to `invalid` and Finish: expect
   validation feedback, no completion, saved profiles unchanged. Restore valid
   modifiers (for example `ctrl+alt`).
3. Finish: expect Saved and active / Setup complete. Quit/relaunch: no automatic
   Settings window (except the documented GTK tray fallback). Open Settings:
   Polish/P, delivery and model are preserved, and the ordinary Apply button is back.
4. Separately launch with existing personal settings: Welcome may appear once;
   verify existing profiles/models/modifiers. Close without Apply, Quit/relaunch:
   they are unchanged and setup is still unfinished.

Close the isolated PowerShell window after quitting the test app. Automated
checks: `python -m unittest discover -s tests -v`,
`python scripts/check_settings_panel.py`, `python scripts/check_desktop.py`.
They do not verify actual speech, model download or physical hardware permissions.
