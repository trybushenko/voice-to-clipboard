# Language profiles

Testing branch: `codex/language-profiles`. Quit the app, switch to this branch,
repeat your platform's pip installation with speech/hotkeys/desktop extras, then
launch the app normally. Do not delete your real settings/history to test defaults.

## Configure

A new installation has only English on Alt+Shift+E, clipboard delivery. Settings
opens at first launch. Add a profile for any other language yourself; there are no
Ukrainian presets on a clean install. English can also be edited or replaced.

In Settings → Language profiles:

1. Choose the Whisper language code (e.g. `pl — Polish`).
2. Choose a unique A–Z letter. All profiles use the shared shortcut modifiers above.
   macOS uses physical ANSI key positions; Alt means Option and Win means Command.
3. Enable Paste with hotkey if desired; otherwise the result goes to clipboard.
4. Leave model override empty for the shared default, or enter a compatible model.
   Empty shared default uses multilingual `large-v3-turbo`; a Ukrainian-specialized
   model is never selected automatically. Custom model language support is your choice;
   known English-only `.en` models are rejected for other languages.
5. Click Add, or select a profile and Update selected. Remove selected deletes it.
6. Click Apply all settings and profiles. Until Apply succeeds, running shortcuts
   and tray actions still use the previous configuration. Registration failures roll back.

At least one profile is required. Pause shortcuts disables all shortcuts without
removing profiles. Tray/Settings recording always copies; automatic paste uses a
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
- Add Polish/P, apply: Alt+Shift+P records Polish. Try copy, then paste in an editor.
- Add/remove Ukrainian explicitly; removal frees its shortcut and removes its menu item.
- Same language with two different keys/models: each selects the intended model.
- Duplicate key, invalid language, non-English with `.en`, occupied native shortcut:
  clear error; previous configuration remains active and saved.
- Restart: profiles persist. Pause/Resume retains exactly these profiles.
- Change settings during recording: rejected; stop first. Second shortcut press
  stops the active session without changing its original language/delivery.
- Existing installation: U/E/L retained, history and selected model preserved.
- Run unit tests and `scripts/check_desktop.py`; the latter does not record audio.

This delivery does not include per-profile modifier sets, a model download wizard,
or automatic validation of arbitrary custom model repositories. Those remain follow-up
work; shared modifiers and per-profile letters are fully configurable now.
