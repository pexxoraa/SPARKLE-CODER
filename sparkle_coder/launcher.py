"""Shared startup logic for the double-click (.pyw) entry point and the
packaged build (see packaging/bootstrap.py). Kept as a real importable
module — a .pyw file's extension is only meaningful to the OS/Windows file
association that launches it, not to Python's own `import` machinery, so
logic that both entry points need has to live here instead of in the .pyw
file itself.
"""
import contextlib
import sys
from pathlib import Path


def show_error(message: str) -> None:
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SPARKLE CODER", message)
        root.destroy()
    except Exception:
        # The included guide is also usable on installations without Tk.
        import webbrowser
        guide = Path(__file__).resolve().parent.parent / "OPEN_FIRST.html"
        if guide.exists():
            webbrowser.open(guide.as_uri())


def launch() -> int:
    if sys.version_info < (3, 11) and not getattr(sys, "frozen", False):
        # A frozen build bundles its own interpreter, so this check only
        # matters for people running the source tree with their own Python.
        show_error("Install Python 3.11 or newer, then reopen SPARKLE CODER. "
                   "The OPEN_FIRST.html file has setup instructions.")
        return 1
    from sparkle_coder.web import main
    from sparkle_coder.webapp import default_app_dir
    from sparkle_coder.workspace import Redactor
    directory = default_app_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        logfile = directory / "launcher.log"
        if logfile.is_symlink():
            raise ValueError("The launcher log must not be a symlink.")
        # pythonw / a windowed frozen build has no console; keep startup
        # messages out of a terminal window that doesn't exist.
        with logfile.open("w", encoding="utf-8") as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                return main()
    except PermissionError:
        show_error("SPARKLE CODER needs permission to save its projects beside the app.\n\n"
                   "Move the whole SPARKLE-CODER folder (or the installed app) to a writable "
                   "location, such as Documents, then open it again. Keep the PROJECTS and "
                   "APP_DATA folders with the app.")
        return 1
    except Exception as exc:
        show_error("SPARKLE CODER could not start.\n\n" + Redactor().text(str(exc)))
        return 1
