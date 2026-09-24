"""Entry point used only by the PyInstaller build (see sparkle_coder.spec).

Not used for normal `python3 Open_SPARKLE_CODER.pyw` runs — those keep
using that file directly, unchanged.

A frozen executable's sys.executable is itself, not a general-purpose
Python interpreter, so sparkle_coder.web can't spawn `[sys.executable,
"picker.py"]` as a subprocess the way it does when run from source. Instead,
web.py re-invokes this same executable with a `--sparkle-picker` marker
argument when frozen, and this file branches on that instead of starting
the full app a second time. See sparkle_coder/web.py's /api/select-folder
handler and sparkle_coder/picker.py.
"""
import sys
from pathlib import Path

# Running this file directly (e.g. `python3 packaging/bootstrap.py`, as
# opposed to via the PyInstaller build) puts packaging/ on sys.path, not the
# project root, so sparkle_coder wouldn't be importable without this. Under
# PyInstaller itself this line is a harmless no-op — its own import
# machinery finds the bundled package regardless.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "--sparkle-picker":
        if len(sys.argv) != 3:
            return 2
        from sparkle_coder.picker import run_picker
        run_picker(sys.argv[2])
        return 0

    # Reuse the exact same startup path as the source-tree .pyw launcher
    # (Open_SPARKLE_CODER.pyw), including its error handling, so packaged
    # and unpackaged behave identically. Both import this real module
    # rather than duplicating logic in the non-importable .pyw file.
    from sparkle_coder.launcher import launch
    return launch()


if __name__ == "__main__":
    raise SystemExit(main())
