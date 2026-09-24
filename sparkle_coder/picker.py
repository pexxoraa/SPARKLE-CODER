"""Run the native folder picker in its own GUI main thread."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


UNAVAILABLE = "Folder chooser is unavailable. Paste the absolute folder path instead."


def run_picker(result_path) -> None:
    root = None
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askdirectory(title="Choose a project folder")
        result = {"path": path}
    except Exception:
        result = {"error": UNAVAILABLE}
    finally:
        if root is not None:
            root.destroy()
    # Windowed executables have no stdout. The parent owns this private temp
    # directory and reads the result only after the helper exits.
    Path(result_path).write_text(json.dumps(result), encoding="utf-8")


def choose_folder():
    with tempfile.TemporaryDirectory(prefix="sparkle-picker-") as temporary:
        result_path = Path(temporary) / "result.json"
        command = ([sys.executable, "--sparkle-picker"] if getattr(sys, "frozen", False)
                   else [sys.executable, str(Path(__file__))])
        try:
            subprocess.run([*command, str(result_path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           timeout=120, check=True,
                           creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            if result_path.stat().st_size > 16384:
                raise ValueError("Oversized picker result")
            result = json.loads(result_path.read_text("utf-8"))
            if isinstance(result, dict) and (isinstance(result.get("path"), str) or isinstance(result.get("error"), str)):
                return result
        except (OSError, ValueError, subprocess.SubprocessError):
            pass
        return {"error": UNAVAILABLE}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(2)
    run_picker(sys.argv[1])
