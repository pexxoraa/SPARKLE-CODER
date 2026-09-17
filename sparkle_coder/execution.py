"""Finite foreground commands with bounded output and optional Docker isolation."""

import os
import signal
import subprocess
import threading
import time
import uuid

from .config import Config
from .workspace import Workspace


def child_environment() -> dict[str, str]:
    allowed = {
        "PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMP", "TEMP", "TMPDIR",
        "SYSTEMROOT", "SystemRoot", "COMSPEC", "PATHEXT", "WINDIR", "USERPROFILE",
        "APPDATA", "LOCALAPPDATA", "VIRTUAL_ENV", "JAVA_HOME", "GOROOT", "GOPATH",
        "CARGO_HOME", "RUSTUP_HOME", "DOTNET_ROOT", "SDKROOT", "DEVELOPER_DIR",
        "SSL_CERT_FILE", "SSL_CERT_DIR",
    }
    result = {key: value for key, value in os.environ.items() if key in allowed}
    result.update({"NO_COLOR": "1", "TERM": "dumb", "CI": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUNBUFFERED": "1"})
    return result


class CommandRunner:
    def __init__(self, workspace: Workspace, config: Config, approve, should_stop=None, observe=None, checkpoint=None):
        self.workspace, self.config, self.approve = workspace, config, approve
        self.should_stop = should_stop or (lambda: False)
        self.observe = observe or (lambda *_: None)
        self.checkpoint = checkpoint or (lambda: None)
        self.denied = set()

    def run(self, command: str, cwd: str = ".", timeout: int | None = None,
            *, trusted: bool = False) -> dict:
        if not isinstance(command, str) or not command.strip() or len(command) > 10000:
            raise ValueError("Command must contain 1–10000 characters.")
        path = self.workspace.path(cwd, directory=True)
        if not path.exists():
            raise ValueError("Command working directory does not exist.")
        if timeout is not None and (type(timeout) is not int or timeout < 1):
            raise ValueError("Command timeout must be a positive integer or omitted.")
        caps = [value for value in (timeout, self.config.command_timeout) if value is not None]
        timeout = min(caps) if caps else None
        self.checkpoint()
        if (command, cwd) in self.denied:
            return {"ok": False, "exit_code": None, "denied": True,
                    "output": "You denied this command in this run. It will not be requested again until you resume."}
        if not trusted and not self.config.auto_approve and not self.approve(command):
            self.denied.add((command, cwd))
            return {"ok": False, "exit_code": None, "denied": True,
                    "output": "Command was not approved. Do not repeat it; report the limitation."}
        if self.should_stop():
            return {"ok": False, "exit_code": None, "cancelled": True,
                    "output": "Task stopped before this command started."}
        container = None
        if self.config.execution == "docker":
            container = "sparkle-coder-" + uuid.uuid4().hex[:12]
            args = ["docker", "run", "--pull=never", "--rm", "--init", "--name", container,
                    "--cap-drop=ALL", "--security-opt=no-new-privileges",
                    "--pids-limit=256", "--memory=4g", "--cpus=2", "--read-only",
                    "--tmpfs", "/tmp:rw,exec,size=512m",
                    "--network", "bridge" if self.config.docker_network else "none",
                    "--mount", f"type=bind,src={self.workspace.root},dst=/workspace",
                    "--tmpfs", "/workspace/.nemotron:rw,noexec,size=16m",
                    "-w", "/workspace" + ("/" + cwd if cwd != "." else ""),
                    "-e", "NO_COLOR=1", "-e", "CI=1", "-e", "PYTHONDONTWRITEBYTECODE=1"]
            if hasattr(os, "getuid"):
                args += ["--user", f"{os.getuid()}:{os.getgid()}"]
            args += [self.config.docker_image, "sh", "-lc", command]
            shell = False
        else:
            args, shell = command, True
        started = time.monotonic()
        process = None
        output, total = bytearray(), [0]

        def consume():
            pending = bytearray()
            while True:
                chunk = os.read(process.stdout.fileno(), 4096)
                if not chunk:
                    break
                total[0] += len(chunk)
                output.extend(chunk)
                if len(output) > 48000:
                    del output[:-48000]
                pending.extend(chunk)
                boundary = pending.rfind(b"\n")
                if boundary >= 0:
                    self.observe("command_output", {"output": bytes(pending[:boundary + 1]).decode("utf-8", errors="replace")})
                    del pending[:boundary + 1]
                if len(pending) > 48000:
                    self.observe("command_output", {"output": "[Long output line omitted from the live log.]\n"})
                    pending.clear()
            if pending:
                self.observe("command_output", {"output": pending.decode("utf-8", errors="replace")})

        def kill():
            if process is None:
                return
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   capture_output=True, timeout=5, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
                    process.kill()
            except (ProcessLookupError, OSError, subprocess.TimeoutExpired):
                process.kill()

        timed_out = False
        cancelled = False
        reader = None
        try:
            self.observe("command_start", {"command": command, "cwd": cwd, "required": trusted,
                                             "timeout": timeout, "environment": self.config.execution})
            process = subprocess.Popen(args, shell=shell, cwd=path, env=child_environment(),
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, start_new_session=os.name == "posix",
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            reader = threading.Thread(target=consume, daemon=True)
            reader.start()
            while process.poll() is None:
                if self.should_stop() or (timeout is not None and time.monotonic() - started >= timeout):
                    cancelled = bool(self.should_stop())
                    timed_out = not cancelled
                    kill()
                    process.wait(timeout=5)
                    break
                try:
                    process.wait(timeout=0.2)
                except subprocess.TimeoutExpired:
                    continue
            reader.join(timeout=2)
            # Background descendants are not supported: do not leak them after a run.
            if os.name == "posix":
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            reader.join(timeout=2)
            text = bytes(output).decode("utf-8", errors="replace")
            if total[0] > len(output):
                text = "[Output truncated; showing the final 48000 bytes.]\n" + text
            if timed_out:
                text += f"\nCommand exceeded its configured {timeout}s timeout. Increase the timeout or leave it blank in settings."
            result = {"ok": process.returncode == 0 and not timed_out and not cancelled,
                    "exit_code": process.returncode, "timed_out": timed_out,
                    "cancelled": cancelled,
                    "seconds": round(time.monotonic() - started, 2), "output": text}
            self.observe("command_end", {k: v for k, v in result.items() if k != "output"})
            return result
        except BaseException:
            kill()
            if process is not None:
                process.wait(timeout=5)
            raise
        finally:
            if container:
                try:
                    subprocess.run(["docker", "rm", "-f", container], capture_output=True,
                                   timeout=10, check=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process and process.stdout and (reader is None or not reader.is_alive()):
                process.stdout.close()
