#!/bin/bash
set -euo pipefail
test "${VTC_DISPOSABLE_CONTAINER:-}" = 1
test -f /.dockerenv
export DEBIAN_FRONTEND=noninteractive
apt-get update
# Test harness only: installed application never imports this Python's packages.
apt-get install -y --no-install-recommends python3 xvfb xauth dbus-x11 ca-certificates
cd /work
export PYTHONPATH=/work/src
xvfb-run -a dbus-run-session -- python3 scripts/check_linux_deb.py /work/artifacts/voice-to-clipboard_0.1.1-1_amd64.deb /reports
