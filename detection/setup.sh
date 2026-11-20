#!/bin/bash
# One-time install (Linux / macOS). Needs Python 3.10+. ~2 GB, CPU only.
set -euo pipefail
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install -q --upgrade pip
if [ "$(uname)" = "Darwin" ]; then .venv/bin/pip install -q -r requirements.txt
else .venv/bin/pip install -q --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt; fi
echo "Ready. Start with ./start.sh"
