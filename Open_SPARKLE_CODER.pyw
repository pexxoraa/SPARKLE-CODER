"""Double-click entry point. Python 3.11+; no package installation is necessary.

Kept intentionally thin: all the real logic lives in sparkle_coder/launcher.py
so it's also importable from the packaged-executable entry point
(packaging/bootstrap.py) — a .pyw file's extension is only meaningful to the
OS's file association, not to Python's own `import` statement.
"""
from sparkle_coder.launcher import launch

if __name__ == "__main__":
    raise SystemExit(launch())
