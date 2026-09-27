#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/../.."
test "$(uname -s)" = Linux
test "$(dpkg --print-architecture)" = amd64
# Build on the oldest supported glibc, with its matching Python GI bindings.
. /etc/os-release
test "${UBUNTU_CODENAME:-${VERSION_CODENAME:-}}" = jammy
python -m PyInstaller --clean --noconfirm packaging/desktop.spec
python packaging/linux/package.py
python -m pip freeze > artifacts/dependencies.txt
