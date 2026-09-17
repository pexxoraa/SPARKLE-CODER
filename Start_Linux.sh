#!/bin/sh
set -eu
launcher_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if command -v python3 >/dev/null 2>&1 && python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 11))' >/dev/null 2>&1; then
    nohup python3 "$launcher_dir/Open_SPARKLE_CODER.pyw" >/dev/null 2>&1 </dev/null &
else
    if command -v zenity >/dev/null 2>&1; then
        zenity --error --title="SPARKLE CODER" --text="Install Python 3.11 or newer with your software manager, then reopen this app." || true
    fi
    if command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$launcher_dir/OPEN_FIRST.html" >/dev/null 2>&1 &
    fi
    exit 1
fi
