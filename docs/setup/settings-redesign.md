# Settings redesign — D.2b

Branch: `codex/settings-redesign`, based on current `origin/main` `bc60d3c`.
This replaces the Tk Settings panel with Qt/PySide6. The existing tray, shortcuts,
dictation, guarded paste and host settings transaction are unchanged. No new
storage format, workflow, delivery mode, model download or audio feature is added.

## Use Settings

- **Languages** opens first: select a profile and Edit, or Add language. Type a
  language to search the supported list, choose a unique A–Z letter, optional
  modifiers and Clipboard/Paste into original field. Save commits in one action;
  Cancel discards the draft. Errors keep your input. A last remaining profile
  cannot be removed. Empty modifiers and model inherit the displayed defaults.
- **General**: overlay (Save General), login startup (takes effect immediately).
- **Advanced**: existing default modifiers, model and inference device (Save Advanced).
  Saving one page does not silently apply another page's draft.
- **Diagnostics**: existing system report, log, pause/resume and Quit. Recording
  remains on the usual shortcuts/tray; Settings adds no home screen or recording flow.
- First run uses the same editor: Save and finish setup. It opens again after an
  interrupted setup, and stops auto-opening after success (except the GTK tray fallback).
- Tab/Shift+Tab navigate, Enter activates a button/list item and Escape cancels the
  profile editor. Labels have mnemonics and accessible names. Colours follow the
  system palette; Qt scales the UI. Scrollable content keeps actions reachable.

## Update commands

Finish any recording, quit the **whole tray app**, and wait for its icon to
vanish. Run these commands from the existing repository with a clean worktree.
The delivery is a review branch; it has not been merged into main.

Windows PowerShell:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
git fetch origin
git switch codex/settings-redesign
git pull --ff-only origin codex/settings-redesign
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

Linux (existing `venv`):

```sh
venv/bin/voice-hotkeys --quit
git fetch origin
git switch codex/settings-redesign
git pull --ff-only origin codex/settings-redesign
venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
venv/bin/python -m voice_to_clipboard.ui.desktop_app
```

On Apple Silicon use native ARM64 Python in your existing venv and replace
`[whisper,hotkeys,desktop]` with `[mac,hotkeys,desktop]`. On Linux the Qt xcb
plugin needs `libxcb-cursor0` and `libxkbcommon-x11-0`; see
[installation prerequisites](installation.md). Do not delete settings/history.
PySide6 is installed with the desktop extra. Tk is still needed for existing
overlay/paste tools on platforms that use them.

## Short manual acceptance

For a clean test without touching personal data, quit the app and use a separate
PowerShell window. After updating, set these variables **before** launching:

```powershell
$vtcSettingsTest = Join-Path $env:TEMP ("vtc-settings-" + [guid]::NewGuid())
$env:VOICE_TO_CLIPBOARD_DATA_DIR = Join-Path $vtcSettingsTest 'data'
$env:VOICE_TO_CLIPBOARD_CACHE_DIR = Join-Path $vtcSettingsTest 'cache'
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

1. Expect only English/E and a short welcome. Set up English and Save: welcome
   disappears. Add Polish/P (or another supported language), clipboard and
   `ctrl+alt` modifiers, Save: the row appears and is immediately active.
2. Edit Polish, set letter E: Save shows a conflict next to the key; the editor
   keeps your input and active shortcuts are unchanged. Cancel: row unchanged.
   Try a non-English profile with `tiny.en`: model error, no saved change.
3. Edit Polish to Paste into original field, Save; remove it and confirm, then
   add it again. Quit/relaunch: profiles, modifiers and delivery persist; first-run
   welcome does not return. Existing custom model overrides/history remain intact.
4. Close Settings, focus a normal editor, start/stop with English then Polish
   shortcuts: clipboard/paste behaves as before. Switching the target field before
   completion must retain text in clipboard and refuse unsafe automatic paste.
5. Use only keyboard in Settings, then try system light/dark and 100/150/200% scale.
   Labels, focus and Save/Cancel must remain readable/reachable. Reopen Settings
   twice: one panel. Pause/Resume and Quit must retain their previous behavior.

Quit the isolated app and close that PowerShell window before normal use.
On Linux use temporary `VOICE_TO_CLIPBOARD_DATA_DIR` and
`VOICE_TO_CLIPBOARD_CACHE_DIR` environment variables for the same isolated test.

## Evidence and limits

- Existing host regression tests cover schema v2/v3, unrelated fields/history,
  completion, registration/write failure rollback, guarded paste and lifecycle.
- Qt smoke uses a simulated host and isolated settings: one Save, Cancel, duplicate
  keys, incompatible/custom models, host rejection and retry, malformed responses,
  old host protection, partial page saves, remove, restart persistence and Quit.
- Local native Linux Qt smoke and tray/host lifecycle smoke passed, without mic,
  model loading or real transcription. Headless Qt interactions passed at
  100/150/200%; light/dark screenshots were inspected. These are simulated DPI
  and palette checks, not physical Windows/macOS display or screen-reader acceptance.
- `python -m unittest discover -s tests -v` includes the Qt smoke when the desktop
  extra is installed. CI also runs native Windows/macOS smoke and offscreen scaling.
- Physical Windows/macOS, screen readers, real voice/GPU/download and installer
  acceptance remain open. OS theme integration varies by desktop; no new theme
  preference is stored. Custom model backend availability is not checked.

Qt references: [search completion](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QCompleter.html)
and [application palette events](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QGuiApplication.html).
