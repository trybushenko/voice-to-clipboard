# Language profiles

Profiles are available on `main`; the Qt Settings UI is in `codex/settings-redesign`.
See [update commands and acceptance](settings-redesign.md). Quit the app, switch to the desired branch,
repeat your platform's pip installation with speech/hotkeys/desktop extras, then
launch the app normally. Do not delete your real settings/history to test defaults.

## Configure

A new installation has only English on Alt+Shift+E, clipboard delivery. Settings
opens at first launch. Add a profile for any other language yourself; there are no
Ukrainian presets on a clean install. English can also be edited or replaced.

In Settings → Languages → Add language or Edit:

1. Choose a language by its full English name (e.g. `Polish (pl)`); the list is alphabetical.
2. Choose a unique A–Z letter. Leave **Profile modifiers** empty to inherit
   **Default shortcut modifiers**, or enter an individual combination such as
   `ctrl+alt`. Supported modifiers: `alt`, `ctrl`, `shift`, `win`, joined with `+`.
   Changing the default affects only profiles without an override.
   macOS uses physical ANSI key positions; Alt means Option and Win means Command.
3. Choose Paste into original field if desired; otherwise choose Clipboard.
4. Leave model override empty for the shared default, or enter a compatible model.
   Empty shared default uses multilingual `large-v3-turbo`; a Ukrainian-specialized
   model is never selected automatically. Custom model language support is your choice;
   known English-only `.en` models are rejected for other languages.
5. Click **Save** (or **Save and finish setup** on first run). One action validates,
   registers and persists the profile. Errors retain your input; Cancel discards it.
6. Select a profile and **Remove**, then confirm, to delete its shortcut. At least
   one profile must remain. Registration failures roll back the saved configuration.

At least one profile is required. Pause shortcuts disables all shortcuts without
removing profiles. Tray recording always copies; automatic paste uses a
hotkey so the original editor field can be captured before recording.

## Migration

Existing settings or default-location history identify a legacy installation and
preserve U/E/L, current modifiers and the global model. Version 2 settings persist
explicit profiles; deleted languages are never re-added on restart. History is not
modified. If you used only a custom history path and never saved preferences, create
your previous shortcuts manually; that installation cannot be identified reliably.

## Acceptance checks

- Fresh isolated user/data directory: only English/E in menu and Settings; no U/L
  registrations and no model download in idle.
- Add Polish/P, Save: Alt+Shift+P records Polish. Try copy, then paste in an editor.
- Add/remove Ukrainian explicitly; removal frees its shortcut and removes its menu item.
- Same language with two different keys/models: each selects the intended model.
- Duplicate key, invalid language, non-English with `.en`, occupied native shortcut:
  clear error; previous configuration remains active and saved.
- Restart: profiles persist. Pause/Resume retains exactly these profiles.
- Change settings during recording: rejected; stop first. Second shortcut press
  stops the active session without changing its original language/delivery.
- Existing installation: U/E/L retained, history and selected model preserved.
- Run unit tests and `scripts/check_desktop.py`; the latter does not record audio.

Individual modifier sets are supported. Letters must still be unique, even when
modifiers differ. Existing version 2 settings keep their inherited modifiers and
are migrated to version 3 on save/startup. Existing overrides from the initial
version 2 branch also survive migration. Older releases reject version 3 rather
than silently deleting individual modifiers; downgrade requires a compatible
settings backup. History is unchanged. The optional profile `modifiers` field
is saved only for explicit overrides.
A model download wizard and validation of arbitrary custom model repositories are
not in the current roadmap; this Settings redesign adds no audio or model features. Quit before
updating: an older running host cannot preserve individual modifiers, and the
updated Settings panel requires a host restart.

## Individual modifier acceptance

1. Keep English/E on the default modifiers. Add Polish/P with `ctrl+alt`.
2. Save, close Settings, and test both shortcuts. Each starts its own language;
   pressing again stops recording. The default modifiers + P must not start Polish.
3. Quit and relaunch. The override remains. Change default modifiers: English
   follows the new default; Polish remains on Ctrl+Alt+P.
4. Clear Polish's Profile modifiers, click Save. Polish
   now uses the default. Invalid modifiers or occupied native shortcuts must
   reject Save and preserve the previous saved and active configuration.
5. Pause/Resume must restore both bindings. Paste-enabled profiles retain the
   existing original-field guard.

## Updating after Windows feedback

Before installing an update, **Quit the tray application**, not just the Settings
window. Or run `.\.venv\Scripts\voice-hotkeys.exe --quit` and wait for the tray
icon to disappear. Pull this branch, reinstall the package, then relaunch. A running
host keeps its old code even after pip installation; incompatible hosts now produce
an explicit restart instruction.

- Add Polish/P and Indonesian/I, Save, wait for **Saved and active**, close Settings,
  then reopen it. Both profiles must remain, and their hotkeys must work.
- Repeat Save followed immediately by closing Settings: the window waits for the
  save acknowledgment. A failed save leaves it open with a reason.
- Remove and confirm a profile, Quit the entire tray app, relaunch: it stays removed.
- Select Bulgarian, Indonesian and other previously unnamed languages by full name.
- Quit app while idle: no Check system or other click is needed to close Settings.
- Test paste from an editor with Settings closed. Genuine focus changes still block
  paste. Connection failures and target-verification failures now have distinct
  messages; include the full detail if the issue persists.

Automated GUI check: `python scripts/check_settings_panel.py` (isolated settings,
no audio). Windows paste/host IPC check: `python scripts/check_paste.py --auto
--overlay --remote-host` (replaces clipboard with test text).
