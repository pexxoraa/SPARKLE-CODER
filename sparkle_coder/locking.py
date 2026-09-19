"""Recover abandoned PID locks without taking a workspace from a live process."""

from contextlib import contextmanager
import os
from pathlib import Path
import stat


class LockError(ValueError):
    """The project cannot currently be locked without risking another writer."""


def process_running(pid):
    """True = present, False = confirmed exited, None = cannot establish ownership.

    PID reuse is deliberately conservative: a live PID is never reclaimed.
    Windows os.kill(pid, 0) is not a safe process probe, so query a process handle.
    """
    if type(pid) is not int or not 0 < pid <= 0x7fffffff:
        return None
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel.WaitForSingleObject.restype = wintypes.DWORD
        kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel.CloseHandle.restype = wintypes.BOOL
        # SYNCHRONIZE permits a zero-timeout wait; no terminate rights are used.
        handle = kernel.OpenProcess(0x00100000, False, pid)
        if not handle:
            return False if ctypes.get_last_error() == 87 else None  # nonexistent PID
        try:
            result = kernel.WaitForSingleObject(handle, 0)
            return {0: False, 258: True}.get(result)
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except (OSError, OverflowError):
        return None


def _regular(info):
    return stat.S_ISREG(info.st_mode) and info.st_nlink == 1


def _identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns


def _read_marker(path):
    """Read a small, unlinked regular file without following a redirected lock."""
    try:
        before = path.lstat()
    except FileNotFoundError:
        return None
    if not _regular(before) or before.st_size > 64:
        raise LockError("The project lock is linked or invalid. Its files were kept for review.")
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    except FileNotFoundError:
        return None  # A legacy owner may release its marker after lstat.
    try:
        info = os.fstat(fd)
        if not _regular(info) or _identity(info) != _identity(before):
            raise LockError("The project lock changed while checking it. Retry the project move.")
        value = os.read(fd, 65)
    finally:
        os.close(fd)
    return info, value


@contextmanager
def _guard(path):
    """A persistent OS-locked file serializes recovery; never unlink this file.

    Closing the descriptor (including on process exit) releases its native lock.
    See docs.python.org/3/library/fcntl.html and /library/msvcrt.html.
    """
    try:
        before = path.lstat()
    except FileNotFoundError:
        before = None
    if before is not None and not _regular(before):
        raise LockError("The project lock guard is linked or invalid. Its files were kept for review.")
    fd = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
                 | getattr(os, "O_NONBLOCK", 0), 0o600)
    acquired = False
    try:
        opened = os.fstat(fd)
        if not _regular(opened) or (before is not None and _identity(before) != _identity(opened)):
            raise LockError("The project lock guard changed. Retry the project move.")
        try:
            if os.name == "nt":
                import msvcrt
                # Byte ranges may extend beyond EOF; use the same byte every time.
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
        except OSError:
            raise LockError("This project is locked by another task, or its drive cannot provide a lock. "
                            "Finish the other task and choose Retry project move.") from None
        # Catch a replaced guard rather than protecting a detached inode.
        if _identity(path.lstat()) != _identity(opened):
            raise LockError("The project lock guard changed. Retry the project move.")
        yield
    finally:
        try:
            if acquired and os.name == "nt":
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        finally:
            os.close(fd)


@contextmanager
def workspace_lock(state_dir):
    state_dir = Path(state_dir)
    if state_dir.is_symlink():
        raise LockError("This project's saved-task folder points to another location. "
                        "The original files were kept; review that folder before moving it.")
    state_dir.mkdir(mode=0o700, exist_ok=True)
    path = state_dir / "workspace.lock"
    with _guard(state_dir / "workspace.guard"):
        marker = _read_marker(path)
        recovered = False
        if marker is not None:
            info, value = marker
            text = value.strip()
            pid = int(text) if text.isdigit() else None
            running = process_running(pid)
            if running is not False:
                if running:
                    raise LockError(f"This project is locked by a running app (process {pid}). "
                                    "Finish its task, use Quit app in that window, then choose Retry project move.")
                raise LockError("SPARKLE could not confirm that the previous task has stopped. "
                                "Its lock was kept. Close the previous app and choose Retry project move. "
                                "If this continues, the saved lock needs review.")
            # Older releases use O_EXCL on this PID file. Compare before deleting
            # and keep O_EXCL below so a legacy app can still win the next claim.
            latest = _read_marker(path)
            if latest is None or _identity(latest[0]) != _identity(info) or latest[1] != value:
                raise LockError("The project lock changed while checking it. Retry the project move.")
            path.unlink()
            recovered = True
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise LockError("Another app just locked this project. Finish its task and retry.") from None
        owned = None
        owner = str(os.getpid()).encode("ascii")
        try:
            os.write(fd, owner)
            owned = os.fstat(fd)
            yield {"recovered": recovered}
        finally:
            os.close(fd)
            try:
                latest = _read_marker(path)
                # Windows can update timestamps on close. Match file identity
                # and ownership bytes rather than pre-close timestamps.
                if (owned is not None and latest is not None and latest[1] == owner
                        and (latest[0].st_dev, latest[0].st_ino) == (owned.st_dev, owned.st_ino)):
                    path.unlink()
            except (FileNotFoundError, LockError):
                pass
