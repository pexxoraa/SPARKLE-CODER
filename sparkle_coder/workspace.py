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
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)
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

    def files(self, pattern: str = "*", limit: int = 1000) -> list[str]:
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
                        if len(result) >= limit:
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
        """Content hash for freshness, excluding generated/secret files; bounded work."""
        digest = hashlib.sha256()
        total = 0
        files = self.files(limit=5001)
        if len(files) > 5000:
            return None
        try:
            for relative in files:
                p = self.path(relative)
                total += p.stat().st_size
                if total > 30_000_000:
                    return None
                digest.update(relative.encode() + b"\0" + p.read_bytes() + b"\0")
        except (OSError, WorkspaceError):
            return None
        return digest.hexdigest()

    @contextmanager
    def lock(self):
        path = self.state_dir / "workspace.lock"
        if path.is_symlink():
            raise WorkspaceError("Workspace lock must not be a symlink.")
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise WorkspaceError(
                "Workspace is locked by another run. If it crashed, check the PID in "
                ".nemotron/workspace.lock and remove that file only after the process has stopped."
            ) from None
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(str(os.getpid()))
            yield
        finally:
            path.unlink(missing_ok=True)
