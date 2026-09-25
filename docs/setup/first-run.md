# First-run setup in Settings

Settings opens until a profile's **Save and finish setup** succeeds. A clean
installation starts with only English/E; existing installations keep their saved
profiles, modifiers and models. Setup completion and profiles are saved in the
same host transaction, after validation and successful shortcut registration.

1. In **Languages**, select **Set up language** or **Add language**.
2. Type a supported language name, choose a unique A–Z shortcut letter and
   **Clipboard** or **Paste into original field**. Empty modifiers inherit the
   default; an empty model override uses the default shown in the editor.
3. Click **Save and finish setup**. Wait for **Saved and active**; subsequent
   profile edits use **Save**. No second Apply step is required.

Cancel discards the editor draft. Closing before a successful Save leaves setup
incomplete; reopening resumes from saved profiles. Failed validation, registration
or persistence leaves the editor open with its input intact. Closing during Save
waits for acknowledgement; a failed Save keeps Settings open. Unsaved General or
Advanced changes require an explicit discard when closing the window.

After completion, Settings no longer opens on every startup, except on Linux
without an embedded GTK tray (the existing fallback). Closing Settings keeps the
tray app running. Use the tray to quit the entire app before updating.

This is configuration only: no microphone test, model download, inference or new
wizard. The host preserves settings v2/v3, unknown fields and history. The existing
optional `onboarding_complete` field is unchanged. Arbitrary custom model support
remains unverified.

The original D.1 implementation was accepted and merged as `1a6e23c`. The current
Qt UI is the D.2b delivery in `codex/settings-redesign`, pending user acceptance.
See [exact update commands and manual checks](settings-redesign.md).
