"""Double-click entry point. Python 3.11+; no package installation is necessary."""

import contextlib
from pathlib import Path
import sys
import webbrowser


def show_error(message):
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("SPARKLE CODER", message)
        root.destroy()
    except Exception:
        # The included guide is also usable on installations without Tk.
        webbrowser.open((Path(__file__).resolve().parent / "OPEN_FIRST.html").as_uri())


def launch():
    if sys.version_info < (3, 11):
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
        # pythonw has no console; keep startup messages out of a terminal window.
        with logfile.open("w", encoding="utf-8") as stream:
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                return main()
    except Exception as exc:
        show_error("SPARKLE CODER could not start.\n\n" + Redactor().text(str(exc)))
        return 1


if __name__ == "__main__":
    raise SystemExit(launch())
