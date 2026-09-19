"""Bounded file operations. These checks are NOT an OS sandbox for shell commands."""

from contextlib import contextmanager
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tempfile

from .locking import LockError, workspace_lock


class WorkspaceError(ValueError):
    pass


IGNORED_DIRS = {
    ".git", ".nemotron", ".venv", "venv", "node_modules", "__pycache__",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".next", ".nuxt",
    "dist", "build", "target", "vendor", ".gradle", ".idea", ".vscode",
}
SECRET_NAMES = {".env", ".netrc", ".npmrc", ".pypirc", "credentials",
                "credentials.json", "id_rsa", "id_ed25519", "nemotron.toml"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}
MAX_FILE_BYTES = 1_000_000
ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")


def clean_terminal(text: str) -> str:
    text = ANSI.sub("", str(text))
    return "".join(c for c in text if c in "\n\t" or (ord(c) >= 32 and ord(c) != 127))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def atomic_write(path: Path, data: bytes, mode: int | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".nemotron-tmp-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if mode is not None:
            os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_json(path: Path, value: object) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2).encode(), 0o600)


class Redactor:
    def __init__(self, extra: tuple[str, ...] = ()):
        self.secrets = sorted({v for k, v in os.environ.items()
                               if len(v) >= 8 and any(s in k.upper() for s in
                                   ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))}
                              | {s for s in extra if len(s) >= 4}, key=len, reverse=True)

    def text(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        return value

    def value(self, value: object) -> object:
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {key: self.value(v) for key, v in value.items()}
        if isinstance(value, list):
            return [self.value(v) for v in value]
        return value


class Workspace:
    def __init__(self, root: Path, *, create: bool = True):
        self.root = root.expanduser().resolve()
        if create:
            self.root.mkdir(parents=True, exist_ok=True)
        elif not self.root.is_dir():
            raise WorkspaceError(f"This project folder is unavailable: {self.root}. "
                                 "Reconnect its drive or use Find folder to choose its current location.")
        self.state_dir = self.root / ".nemotron"
        if self.state_dir.is_symlink():
            raise WorkspaceError(".nemotron must not be a symlink.")
        self.state_dir.mkdir(mode=0o700, exist_ok=True)

    @staticmethod
    def protected(parts: tuple[str, ...]) -> bool:
        return any(p in IGNORED_DIRS or p.lower() in SECRET_NAMES or
                   p.lower().startswith(".env.") or
                   Path(p).suffix.lower() in SECRET_SUFFIXES for p in parts)

    def path(self, relative: str, *, directory: bool = False) -> Path:
        if not isinstance(relative, str) or "\x00" in relative or "\\" in relative:
            raise WorkspaceError("Use a workspace-relative path with forward slashes.")
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts or ":" in relative:
            raise WorkspaceError("Absolute paths and parent traversal are not allowed.")
        if self.protected(rel.parts):
            raise WorkspaceError("This path is protected or excluded from agent file tools.")
        path = self.root
        for part in rel.parts:
            path = path / part
            if path.is_symlink():
                raise WorkspaceError("Symlinks are not followed by agent file tools.")
        if not path.resolve().is_relative_to(self.root):
            raise WorkspaceError("Path escapes the workspace.")
        if path == self.root and not directory:
            raise WorkspaceError("A file path is required.")
        if path.exists():
            info = path.stat()
            if not directory and not stat.S_ISREG(info.st_mode):
                raise WorkspaceError("Only regular files are supported.")
            if not directory and info.st_nlink > 1:
                raise WorkspaceError("Hard-linked files are not editable through file tools.")
            if directory and not path.is_dir():
                raise WorkspaceError("Expected a directory.")
        return path

    def files(self, pattern: str = "*", limit: int | None = 1000) -> list[str]:
        result = []
        for base, dirs, names in os.walk(self.root, followlinks=False):
            dirs[:] = sorted(d for d in dirs if not self.protected((d,))
                             and not (Path(base) / d).is_symlink())
            for name in sorted(names):
                p = Path(base) / name
                relative = p.relative_to(self.root).as_posix()
                if not self.protected((name,)) and not p.is_symlink() and p.is_file():
                    if fnmatch.fnmatch(relative, pattern):
                        result.append(relative)
                        if limit is not None and len(result) >= limit:
                            return result
        return result

    def read(self, relative: str) -> tuple[str, str]:
        path = self.path(relative)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise WorkspaceError(f"File exceeds {MAX_FILE_BYTES} bytes; use a narrower command.")
        data = path.read_bytes()
        if b"\x00" in data:
            raise WorkspaceError("Binary files cannot be read as text.")
        return data.decode("utf-8"), sha256(data)

    def instructions(self, relative: str = "placeholder") -> str:
        path = self.path(relative)
        guides = []
        parent = path.parent
        parents = [self.root]
        if parent != self.root:
            parents += list(reversed([p for p in parent.parents if p != self.root
                                      and p.is_relative_to(self.root)])) + [parent]
        for folder in dict.fromkeys(parents):
            guide = folder / "AGENTS.md"
            if guide.is_file() and not guide.is_symlink():
                text, _ = self.read(guide.relative_to(self.root).as_posix())
                guides.append(f"{guide.relative_to(self.root)}:\n{text[:12000]}")
        return "\n\n".join(guides)[:24000]

    def fingerprint(self) -> str | None:
        """Stream project contents so large projects can also have fresh checks."""
        digest = hashlib.sha256()
        try:
            for relative in self.files(limit=None):
                p = self.path(relative)
                digest.update(relative.encode() + b"\0")
                with p.open("rb") as stream:
                    for chunk in iter(lambda: stream.read(128 * 1024), b""):
                        digest.update(chunk)
                digest.update(b"\0")
        except (OSError, WorkspaceError):
            return None
        return digest.hexdigest()

    @contextmanager
    def lock(self):
        try:
            with workspace_lock(self.state_dir) as status:
                yield status
        except LockError as exc:
            raise WorkspaceError(str(exc)) from None
