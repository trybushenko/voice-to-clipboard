#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
test "$(uname -s)" = Darwin
test "$(uname -m)" = arm64
python -c 'import platform; assert platform.machine() == "arm64"'
python -m PyInstaller --clean --noconfirm packaging/desktop.spec
version=$(python -c 'import tomllib; print(tomllib.load(open("pyproject.toml", "rb"))["project"]["version"])')
stage=$(mktemp -d)
trap 'rm -rf "$stage"' EXIT
ditto dist/VoiceToClipboard.app "$stage/VoiceToClipboard.app"
ln -s /Applications "$stage/Applications"
mkdir -p artifacts
name="VoiceToClipboard-${version}-macos-arm64-preview.dmg"
hdiutil create -volname 'Voice to Clipboard' -srcfolder "$stage" -ov -format UDZO "artifacts/$name"
(cd artifacts && shasum -a 256 "$name" > "$name.sha256")
python -m pip freeze > artifacts/dependencies.txt
python - <<'PY'
import json, platform, subprocess, tomllib
from pathlib import Path
version = tomllib.loads(Path('pyproject.toml').read_text())['project']['version']
Path('artifacts/build.json').write_text(json.dumps(dict(version=version,
    commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
    architecture='arm64', minimum_macos='14.0', build_os=platform.platform(),
    signing='ad-hoc only; no Developer ID', notarized=False, models_included=False), indent=2))
PY
