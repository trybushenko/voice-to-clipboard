# Development

Install the package before running tools (Python 3.10+):

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
python tests/unit/test_gate.py
```

`tests/unit/` covers recording, speech gating, history, backend adapters and desktop
dispatch. `tests/integration/` covers IPC, persistent worker reuse and installed
entry points. Tests use synthetic audio and fake models: no microphone, GPU,
model downloads or clipboard mutation. The gate script prints diagnostic scenarios.

To run from another working directory, use the installed environment's Python and
absolute paths to `tests/` or the diagnostic script. CI installs a regular package
on Linux, Windows and macOS with Python 3.11/3.12.

## Source map

- `cli.py`: arguments and session orchestration; `__main__.py`: module entry point.
- `core/`: recording, speech gate, transcription queue, history and stop listener.
- `backends/`: faster-whisper and MLX adapters with backend selection.
- `worker/`: service, client, message framing, transport and runtime configuration.
- `platform/`: storage paths, desktop operations, locks and Windows clipboard.
- `ui/`: overlay, terminal meter and global hotkey host.

Platform operations still dispatch through `platform/desktop.py`. Additional OS
modules, tray UI, setup helpers and installers will be added with their actual
implementation in later roadmap stages.

## Compatibility and subprocesses

`dictate`, `voice-to-clipboard` and `voice-hotkeys` remain installed console commands.
`python -m voice_to_clipboard` is the package entry point. Workers launch with
`python -m voice_to_clipboard.worker.service` using the same environment as the
client. Install after updating source so subprocesses also use the new package.

The root `dictate.py` intentionally stays as a small source-tree bootstrap for
existing Linux launchers referencing its absolute path. It imports `src/` when
available, otherwise the installed package. It contains no application logic.
Existing data/cache paths and `DICTATE_HISTORY`/`DICTATE_RUNTIME` are unchanged.

## Optional desktop and model checks

From the repository root:

```sh
/usr/bin/python3 scripts/check_overlay.py
python scripts/benchmark_worker.py
python scripts/check_paste.py
```

The Linux X11 overlay check shows a six-second demo, checks focus and cleanup,
and saves `/tmp/dictate-overlay.png`. It needs GTK3, xdotool and xprop.
It locates this checkout's `src/` itself because the system GTK Python may differ
from the application's virtualenv. The overlay subprocess intentionally launches
its own absolute Python file with no package imports, preserving system GTK access.

The benchmark requires the installed speech backend and cached model weights;
it uses an isolated temporary worker with synthetic silence. It never records.
`scripts/configure-dictation.py` updates the existing development GNOME bindings;
its backups remain in the ignored repository `backups/` folder.

## Release packaging check

```sh
python -m pip wheel --no-deps . -w dist
```

Install the wheel in a fresh virtualenv, change to another directory, and run all
three commands with `--help` plus the tests using an absolute discovery path.
This detects imports accidentally resolved from the checkout or old flat modules.

`check_paste.py` opens an isolated test field and verifies exact Unicode insertion
using the platform clipboard/input APIs; it puts synthetic text in the clipboard.
Use `--auto` for an unattended GUI check on an interactive desktop.
