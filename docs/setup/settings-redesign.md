# Settings redesign — D.2b

Accepted by the user on 2026-09-25 and merged into `main` as `f9c3236`.
The completed remote branch `codex/settings-redesign` was deleted. Base: `bc60d3c`.
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
The delivery is available on main.

Windows PowerShell:

```powershell
.\.venv\Scripts\voice-hotkeys.exe --quit
git fetch origin
git switch main
git pull --ff-only origin main
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys,desktop]"
.\.venv\Scripts\python.exe -m voice_to_clipboard.ui.desktop_app
```

Linux (existing `venv`):

```sh
venv/bin/voice-hotkeys --quit
git fetch origin
git switch main
git pull --ff-only origin main
venv/bin/python -m pip install '.[whisper,hotkeys,desktop]'
venv/bin/python -m voice_to_clipboard.ui.desktop_app
```

On Apple Silicon use native ARM64 Python in your existing venv and replace
`[whisper,hotkeys,desktop]` with `[mac,hotkeys,desktop]`. On Linux Qt needs `libegl1`/`libgl1`; its xcb
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

Implementation: `dc1d720`; Linux Qt runtime prerequisites: `b5aab52`.
[CI for b5aab52](https://github.com/trybushenko/voice-to-clipboard/actions/runs/36128646652)
passed all six jobs: Windows/macOS/Linux, Python 3.11/3.12. This includes native
Windows/macOS Settings/lifecycle, Windows remote-guard paste and Qt scaling.
The initial Ubuntu run exposed missing libEGL; CI and setup prerequisites now
include it. Local final suite: 99 tests passed, 4 platform skips.


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
  acceptance remain open. The user confirmed the listed manual scenarios on
  2026-09-25; no separate hardware/OS matrix was supplied. OS theme integration varies by desktop; no new theme
  preference is stored. Custom model backend availability is not checked.

Qt references: [search completion](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QCompleter.html)
and [application palette events](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QGuiApplication.html).


## Local repository relocation (2026-09-25)

The local checkout and its existing venv now live at
`/home/artem-trybushenko/Projects/voice-to-clipboard`. The standard Linux data
folder remains `~/.local/share/dictate`: history, settings and backups belong
there and are unchanged. Models/caches and GNOME U/E/L bindings are unchanged.
The `~/.local/bin/dictate` launcher and venv launch scripts use the new paths,
including the existing NVIDIA library paths. The package was reinstalled from
its new location without changing speech/CUDA dependencies.

A private backup of data, the old launcher and GNOME bindings is in
`~/.local/share/dictate/backups/relocation-2026-09-25`. Checksum comparison verified
that personal data was preserved. Open the new Projects folder for development;
the old data directory is no longer a Git checkout.

Post-move verification: 99 tests OK (4 platform skips), native desktop lifecycle
smoke OK, `~/.local/bin/dictate --help` from `/tmp` OK. History checksum and GNOME
bindings were checked again after reinstall/tests and remained unchanged.
