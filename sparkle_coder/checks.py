"""Discover existing, finite project checks without executing project code."""

import json
import os
from pathlib import PurePosixPath
import re
from .python_runtime import python_argv, shell_command


def package_manager(data, names, root="."):
    declared = data.get("packageManager", "") if isinstance(data, dict) else ""
    if isinstance(declared, str) and declared.split("@")[0] in ("npm", "pnpm", "yarn", "bun"):
        return declared.split("@")[0]
    prefix = "" if root == "." else root + "/"
    return next((manager for lock, manager in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"),
                ("bun.lock", "bun"), ("bun.lockb", "bun")) if prefix + lock in names), "npm")


def discover_checks(workspace, execution="local", *, files=None):
    files = workspace.files(limit=10001) if files is None else files
    names = set(files)
    manifests = {"package.json", "pyproject.toml", "pytest.ini", "setup.cfg", "Cargo.toml", "go.mod"}
    roots = {"."}
    for name in files:
        path = PurePosixPath(name)
        if path.name in manifests and len(path.parts) <= 4:
            roots.add(str(path.parent))
    checks = []

    def read(path):
        try:
            return workspace.read(path)[0]
        except (OSError, ValueError, UnicodeError):
            return ""

    def add(command, cwd, source):
        checks.append({"command": command, "cwd": cwd, "source": source})

    for root in sorted(roots, key=lambda item: (item != ".", item)):
        argv = ["python3"] if execution == "docker" else python_argv(workspace.root / root)
        # Keep a discoverable candidate when Python is absent. Setup inspection
        # explains the missing interpreter; never substitute the frozen GUI.
        argv = argv or (["py", "-3"] if os.name == "nt" else ["python3"])
        python = shell_command(argv, docker=execution == "docker")
        prefix = "" if root == "." else root + "/"
        manifest = prefix + "package.json"
        if manifest in names:
            data = {}
            try:
                data = json.loads(read(manifest))
                scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
                if not isinstance(scripts, dict):
                    scripts = {}
            except ValueError:
                scripts = {}
            manager = package_manager(data, names, root)
            for key in ("typecheck", "type-check", "check", "lint", "test", "build"):
                script = scripts.get(key)
                if not isinstance(script, str) or not script.strip():
                    continue
                if re.search(r"(?:--watch|\bwatch\b|\bserve\b|\bdev\b|no test specified)", script):
                    continue
                add(f"{manager} run {key}", root, manifest + " scripts." + key)
        if prefix + "Cargo.toml" in names:
            add("cargo test", root, prefix + "Cargo.toml")
        if prefix + "go.mod" in names:
            add("go test ./...", root, prefix + "go.mod")
        tests = [name for name in files if name.startswith(prefix) and (
            PurePosixPath(name).name.startswith("test_") or PurePosixPath(name).name.endswith("_test.py"))
            and name.endswith(".py") and not any(
                other != root and other != "." and name.startswith(other + "/")
                and (root == "." or other.startswith(prefix)) for other in roots)]
        if tests:
            samples = "\n".join(read(name)[:16000] for name in tests[:20])
            configuration = read(prefix + "pyproject.toml") + read(prefix + "setup.cfg")
            if prefix + "pytest.ini" in names or "pytest" in configuration or re.search(r"\b(?:import|from) pytest\b", samples):
                add(python + " -m pytest", root, "Python test suite")
            elif re.search(r"\b(?:import|from) unittest\b", samples):
                start = "tests" if any(name.startswith(prefix + "tests/") for name in tests) else "."
                add(python + " -m unittest discover -s " + start + " -v", root, "Python unittest suite")
    return {"checks": checks, "scan_truncated": len(files) > 10000,
            "note": "Candidates from project files; commands require normal approval. "
                    "Inspect runner configuration and add task-specific behavioral checks as needed."}
