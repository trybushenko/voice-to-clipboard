#!/bin/bash
set -euo pipefail
test "${VTC_DISPOSABLE_CONTAINER:-}" = 1
test -f /.dockerenv
export DEBIAN_FRONTEND=noninteractive
apt-get update
# Test harness only: installed application never imports this Python's packages.
apt-get install -y --no-install-recommends python3 xvfb xauth dbus-x11 dunst ca-certificates
cd /work
export PYTHONPATH=/work/src
shopt -s nullglob
packages=(/work/artifacts/voice-to-clipboard_*_amd64.deb)
test "${#packages[@]}" -eq 1
xvfb-run -a dbus-run-session -- python3 scripts/check_linux_deb.py "${packages[0]}" /reports
