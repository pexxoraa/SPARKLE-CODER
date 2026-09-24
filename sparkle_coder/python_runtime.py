"""Locate a project interpreter without executing it or importing project code."""

import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def python_argv(project=None):
    """A frozen GUI is never a Python interpreter. Prefer the project's venv."""
    frozen = getattr(sys, "frozen", False)

    def usable(value):
        if not value:
            return None
        path = Path(value).expanduser()
        if path.name.lower() == "pythonw.exe":
            path = path.with_name("python.exe")
        if not path.is_file() or not os.access(path, os.X_OK):
            return None
        resolved = path.resolve()
        if frozen and (resolved == Path(sys.executable).resolve() or
                       (getattr(sys, "_MEIPASS", None) and resolved.is_relative_to(Path(sys._MEIPASS).resolve()))):
            return None
        # Keep the venv path: resolving its symlink would discard its environment.
        return [str(path.absolute())]

    if project is not None:
        for name in (".venv", "venv"):
            candidate = Path(project) / name / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if found := usable(candidate):
                return found
    configured = os.environ.get("SPARKLE_PYTHON", "").strip()
    if configured:
        return usable(shutil.which(configured) or configured)
    if not frozen and (found := usable(sys.executable)):
        return found
    if frozen:
        bundled = Path(sys.executable).resolve().parent / 'runtime' / 'python'
        for relative in ('python.exe', 'bin/python3', 'bin/python'):
            if found := usable(bundled / relative):
                return found
    for name in ("python3", "python"):
        if found := usable(shutil.which(name)):
            return found
    if os.name == "nt" and (found := usable(shutil.which("py"))):
        return found + ["-3"]
    return None


def shell_command(parts, *, docker=False):
    return subprocess.list2cmdline(parts) if os.name == "nt" and not docker else shlex.join(parts)


def python_command(*args, project=None):
    parts = python_argv(project)
    if parts is None:
        raise ValueError("Python for running project code was not found. Install Python 3.11 or newer "
                         "and enable it on PATH, then reopen SPARKLE CODER. The app's bundled Python "
                         "only runs the interface. Advanced: set SPARKLE_PYTHON to your interpreter path.")
    return shell_command([*parts, *args])
