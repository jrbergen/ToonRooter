#!/bin/sh
# Run manually on a prepared Pi, with Toon disconnected. Never edits system config.
set -eu
if [ "$(id -u)" -eq 0 ]; then
    echo "Run as your normal user; install apt prerequisites separately." >&2
    exit 1
fi
repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
venv_dir=${1:-"$repo_dir/.venv"}
python_cmd=${PYTHON:-python3}
"$python_cmd" -c 'import sys; assert sys.version_info >= (3, 12), "Python >=3.12 required"'
if [ -e "$venv_dir" ] && [ ! -x "$venv_dir/bin/python" ]; then
    echo "Existing destination is not a virtual environment; refusing." >&2
    exit 1
fi
if [ ! -e "$venv_dir" ]; then
    "$python_cmd" -m venv "$venv_dir"
fi
"$venv_dir/bin/python" -c 'import sys; assert sys.version_info >= (3, 12), "Venv Python >=3.12 required"'
"$venv_dir/bin/python" -m pip install "$repo_dir"
echo "Installed host tools. No GPIO/UART, target OpenOCD or system configuration touched."
echo "Run: $venv_dir/bin/toonrooter doctor --repository $repo_dir"
