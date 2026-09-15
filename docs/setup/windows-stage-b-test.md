# Windows acceptance: stage B

Testing branch: `codex/windows-worker-lifecycle`. Do not merge until the Windows
checks below pass. This branch addresses worker/IPC/Ctrl+C; automatic startup,
stray shortcut letters and paste reliability remain separate roadmap work.

## Update an existing checkout

Close the old hotkey host and finish any active recording first. From the repository
folder in PowerShell, with a clean working tree:

```powershell
git fetch origin
git switch --track origin/codex/windows-worker-lifecycle
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

If the branch already exists locally, use `git switch codex/windows-worker-lifecycle`
and `git pull --ff-only` instead. If your environment is called `venv`, replace
`.venv` accordingly. If none exists, first run `py -3.12 -m venv .venv`.
No environment activation or execution-policy changes are needed.

Before the first recording, stop the idle worker from the previous installation:

```powershell
.\.venv\Scripts\dictate.exe --unload-model
```

If it is busy, finish the recording first. Do not terminate unrelated Python processes.

## Checks

1. Run `dictate.exe --lang uk --overlay` using the full path above. Speak a sentence
   with distinctive words at the end. Press Ctrl+C while speaking: recording must
   end, final words must reach the clipboard, and the command must finish.
2. Repeat while the model is still loading on the first recording, and with a warm
   model. Repeat 20 times. No WinError 10054, lost tail or duplicate final text.
3. Check the worker PID before and after Ctrl+C and the next recording (within its
   five-minute idle timeout). It must remain the same:

   ```powershell
   Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'voice_to_clipboard.worker.service' } | Select-Object ProcessId, ParentProcessId, CommandLine
   ```

4. Run `.\.venv\Scripts\voice-hotkeys.exe`. Test Alt+Shift+U/E. Ctrl+C in its console
   must stop the host and print confirmation. During a recording, quitting must
   finish recording/transcription first. A second Ctrl+C while draining explicitly
   cancels only the host's own recording processes.
5. Test closing the console window separately from Ctrl+C. Record the worker PID
   before/after. Console closure is still an open acceptance item; do not assume
   process-group isolation covers it.
6. If CUDA is installed, repeat with `--inference-device cuda` on both commands.
   For a CPU comparison use `--inference-device cpu`. `--one-shot` may be used as
   a diagnostic comparison, but does not validate the persistent worker fix.

Automatic paste and leaked U/L characters are not acceptance criteria for stage B;
they remain stage C. A no-terminal app/autostart remains future desktop work.

## Feedback

Send Windows/Python versions, CPU/CUDA mode, test results, any complete traceback,
and worker PID before/after the failing action. Note whether the model was cold,
warm or still loading, and whether you used Ctrl+C or closed the console window.
Do not include private transcripts or audio.

## Return to main

After finishing recording, stop the host and unload the idle worker. Then:

```powershell
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install ".[whisper,hotkeys]"
```
