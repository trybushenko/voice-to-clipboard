# macOS ARM64 app / DMG preview (E.3)

Branch: `codex/macos-arm64-dmg`, based on `origin/main` `dfae012`.
Native Apple Silicon only, macOS 14 or newer; no Python, Git or Rosetta needed
on the target Mac. Models download separately on first use. Existing Settings,
profiles, history and model/cache paths are unchanged. Existing explicit backend
choices are preserved; ARM64 `auto` continues to select MLX/Metal.

This is an **ad-hoc signed preview**, without Developer ID or notarization.
It is not a public signed release. Gatekeeper may block it; use the normal
Privacy & Security “Open Anyway” flow only after verifying the source/checksum.
Do not disable Gatekeeper globally. Physical Mac M4 permissions, microphone,
Metal transcription and login startup still require manual acceptance.

## Download and install

Download `macos-arm64-dmg` from the successful **macOS ARM64 DMG** Actions run
for this branch. It contains the DMG, SHA256, build metadata, dependencies and
verification reports. With GitHub CLI (optional, for downloading only):

```sh
gh run list --repo trybushenko/voice-to-clipboard --workflow macos-dmg.yml --branch codex/macos-arm64-dmg
# Substitute the successful run ID from the list:
gh run download RUN_ID --repo trybushenko/voice-to-clipboard --name macos-arm64-dmg --dir macos-preview
cd macos-preview
shasum -a 256 -c VoiceToClipboard-0.1.1-macos-arm64-preview.dmg.sha256
open VoiceToClipboard-0.1.1-macos-arm64-preview.dmg
```

Expected checksum: `OK`. In Finder copy `VoiceToClipboard.app` into
`/Applications` (the DMG shortcut), or `~/Applications` for a per-user install.
Eject the DMG and launch the installed copy. Do not run from the mounted image.
Finish the existing Settings setup and grant requested macOS permissions.
The app refuses login startup from a mounted/translocated bundle.

## Update, login startup and removal

Finish dictation and choose menu bar **Quit** before replacing or deleting the
app. Replace the entire installed `.app` using Finder **Replace**; do not merge
its Contents. Keep the same location so an enabled LaunchAgent still points to
it. Reopen the new app. There is no automatic updater or running-update blocker;
do not replace a running bundle. Version remains project version 0.1.1; use the
commit in `build.json` to distinguish previews.

**Start at login** uses the existing single per-user LaunchAgent label
`com.trybushenko.voicetoclipboard`. Enabling replaces that app-specific agent;
it does not add a second mechanism. Disabled means its matching file is absent.
Changes apply to the next login; disabling does not quit the current app.
When switching from a source installation, Quit that instance and enable startup
in the installed app. The old source app/venv is not deleted automatically.
If you move the app, enable startup again at its new location.

To uninstall, disable **Start at login**, Quit, then move the installed app to
Trash. Deleting the app alone does not remove its LaunchAgent. Optional terminal
cleanup before moving the app to Trash (after Quit):

```sh
/Applications/VoiceToClipboard.app/Contents/MacOS/VoiceToClipboard --uninstall
```

This command removes only the matching startup file; Finder removes the bundle.
A startup entry now owned by another install is retained. Settings, history,
profiles and downloaded models remain and are reused on reinstall. No source
Python launcher or user data directory needs deletion.

## Build and automated checks

On native ARM64 macOS with Python 3.12:

```sh
git fetch origin
git switch codex/macos-arm64-dmg
git pull --ff-only
python -m pip install -r packaging/requirements.txt '.[mac,whisper,hotkeys,desktop]'
bash packaging/macos/build.sh
```

CI mounts the DMG, copies to Applications in a disposable account, checks native
ARM64 and bundle metadata, exercises frozen Qt/native imports/worker/overlay and
desktop lifecycle, replaces the whole bundle, toggles the startup file and
uninstalls/reinstalls. `check_macos_dmg.py` refuses non-CI use. It does not simulate
an actual logout/login, TCC grants, microphone or physical Metal dictation.
Unit checks cover ownership, unsupported install paths and retained data.

## Short physical Mac M4 acceptance

1. Install and launch: one menu bar app, existing first-run Settings, no terminal
   or Python required. Grant Microphone/Accessibility/Input Monitoring as asked.
2. With backend `auto`, dictate a short English sentence using the configured
   shortcut, stop and paste manually: expected recognizable text in clipboard,
   no stray shortcut character. Record macOS version/model/backend and result.
3. Save another language profile; Quit/relaunch: profile persists. Enable login
   startup, log out/in: one app starts. Disable, log out/in: no app starts.
4. Quit, replace the entire app at the same path, reopen: profiles and history
   persist; an enabled login entry remains valid. Repeat a recording.
5. Disable startup, Quit, Trash app, reinstall: saved profiles/history remain;
   startup stays disabled. Quit releases the microphone and a new launch works.

Record these results separately from CI; E.3 physical acceptance remains open
until they are supplied. Signing/notarization, Intel builds, Linux packages and
NVIDIA runtime are outside this delivery.
