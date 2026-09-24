"""Loopback-only browser application, with per-launch authentication and CSRF checks."""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import threading
import urllib.request
from urllib.parse import parse_qs, quote, urlsplit
import webbrowser

from .webapp import AppService, default_app_dir, legacy_app_dirs
from .files import UserFiles
from .picker import choose_folder
from . import __version__
from .workspace import Redactor, write_json


STATIC = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"),
          "/app.css": ("app.css", "text/css"), "/favicon.svg": ("favicon.svg", "image/svg+xml")}


def website_origin(value):
    if not isinstance(value, str) or len(value) > 2048:
        raise ValueError("Paste your SPARKLE CODER website address.")
    parsed = urlsplit(value.strip())
    local = parsed.hostname in ("127.0.0.1", "localhost")
    if (not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ("", "/") or any(c.isspace() for c in value)
            or (parsed.scheme != "https" and not (local and parsed.scheme == "http"))
            or parsed.hostname == "null" or "*" in parsed.netloc):
        raise ValueError("Use the HTTPS home address of your SPARKLE CODER website, without a path or sign-in details.")
    port = parsed.port  # Validates the port instead of accepting malformed origins.
    default = 443 if parsed.scheme == "https" else 80
    hostname = parsed.hostname.encode("idna").decode("ascii")
    return f"{parsed.scheme}://{hostname}" + (f":{port}" if port and port != default else "")


class LocalServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, service):
        super().__init__(address, Handler)
        self.service = service
        self.token = secrets.token_urlsafe(32)
        self.origin = f"http://127.0.0.1:{self.server_port}"
        self.hosts = {f"127.0.0.1:{self.server_port}", f"localhost:{self.server_port}"}
        self.origins = {"http://" + host for host in self.hosts}
        self.hosted_origin = None
        self.hosted_token = None
        self.pairing_lock = threading.RLock()

    def pair_website(self, url):
        origin = website_origin(url)
        with self.pairing_lock:
            self.hosted_origin = origin
            self.hosted_token = secrets.token_urlsafe(32)
            # Fragments never go to Vercel or appear in HTTP request logs.
            return {"origin": origin, "url": origin + "/#engine=" + quote(self.origin, safe="")
                    + "&token=" + quote(self.hosted_token, safe="")}


class Handler(BaseHTTPRequestHandler):
    server_version = "SparkleCoder"

    def log_message(self, *args):
        pass

    def send(self, status, data, content_type="application/json", extra_headers=None):
        if content_type == "application/json":
            data = json.dumps(data, ensure_ascii=False).encode("utf-8")
        elif isinstance(data, str):
            data = data.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type != "image/svg+xml" else ""))
        self.send_header("Content-Length", str(len(data)))
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        origin = self.headers.get("Origin")
        if origin and origin == self.server.hosted_origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy",
                         "default-src 'self'; script-src 'self'; style-src 'self'; "
                         "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
                         "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        self.end_headers()
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def guard(self, api=False):
        if self.headers.get("Host") not in self.server.hosts:
            self.send(403, {"error": "Unrecognized host."})
            return False
        origin = self.headers.get("Origin")
        hosted = bool(origin and origin == self.server.hosted_origin)
        if origin and origin not in self.server.origins and not (api and hosted):
            self.send(403, {"error": "Cross-origin requests are not allowed."})
            return False
        if self.headers.get("Sec-Fetch-Site") == "cross-site" and api and not hosted:
            self.send(403, {"error": "Cross-site API requests are not allowed."})
            return False
        expected = self.server.hosted_token if hosted else self.server.token
        if api and (not expected or not secrets.compare_digest(self.headers.get("X-Sparkle-Token", "").encode("utf-8"),
                                                               expected.encode("utf-8"))):
            self.send(401, {"error": "Reopen the app using its desktop launcher to reconnect."})
            return False
        return True

    def do_OPTIONS(self):
        origin = self.headers.get("Origin")
        requested_headers = {name.strip().lower() for name in self.headers.get("Access-Control-Request-Headers", "").split(",") if name.strip()}
        if (self.headers.get("Host") not in self.server.hosts or not urlsplit(self.path).path.startswith("/api/")
                or not origin or origin != self.server.hosted_origin
                or self.headers.get("Access-Control-Request-Method") not in ("GET", "POST")
                or requested_headers - {"content-type", "x-sparkle-token"}):
            self.send(403, {"error": "Connect this website from the local SPARKLE CODER app first."})
            return
        headers = {"Access-Control-Allow-Methods": "GET, POST", "Access-Control-Allow-Headers": "Content-Type, X-Sparkle-Token",
                   "Access-Control-Max-Age": "60"}
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            headers["Access-Control-Allow-Private-Network"] = "true"
        self.send(204, "", "text/plain", headers)

    def download(self, data, name, content_type="application/octet-stream"):
        self.send(200, data, content_type, {"Content-Disposition": "attachment; filename*=UTF-8''" + quote(name, safe="")})

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        if not self.guard(path.startswith("/api/")):
            return
        if path in STATIC:
            name, content_type = STATIC[path]
            self.send(200, (Path(__file__).parent / "ui" / name).read_bytes(), content_type)
            return
        query = parse_qs(parsed.query)
        parts = path.strip("/").split("/")
        app = self.server.service
        try:
            if path == "/api/state":
                result = app.state()
                result["hosted_ui"] = {"origin": self.server.hosted_origin}
            elif len(parts) == 3 and parts[:2] == ["api", "runs"]:
                job = app.job(parts[2])
                result = job.public(int(query.get("after", ["0"])[0]))
                if result["session_id"]:
                    result["session"] = app.snapshot(result["project_id"], result["session_id"], include_events=False)
            elif len(parts) >= 4 and parts[:2] == ["api", "projects"]:
                project_id, operation = parts[2:4]
                project, workspace = app.project(project_id)
                user_files = UserFiles(workspace.root)
                if operation == "files":
                    listing = user_files.files(limit=3001)
                    result = {"files": listing[:3000], "truncated": len(listing) > 3000}
                elif operation == "brief" and len(parts) == 4:
                    result = app.project_context(project_id)
                elif operation == "setup" and len(parts) == 4:
                    result = app.setup(project_id)
                elif operation == "file":
                    relative = query.get("path", [""])[0]
                    result = user_files.preview(relative)
                    result["content"] = Redactor(tuple(app.keys.values())).text(result["content"])
                elif operation == "download":
                    relative = query.get("path", [""])[0]
                    self.download(user_files.bytes(relative), Path(relative).name)
                    return
                elif operation == "download-project":
                    data = app.file_action(project_id, "download-project")
                    self.download(data, "project-" + project_id + ".zip", "application/zip")
                    return
                elif operation == "export-manifest":
                    result = user_files.manifest()
                elif operation == "sessions" and len(parts) == 4:
                    result = {"sessions": app.history(project_id)}
                elif operation == "sessions" and len(parts) in (5, 6):
                    session_id = parts[4]
                    if len(parts) == 5:
                        result = app.snapshot(project_id, session_id)
                    elif parts[5] == "changes":
                        result = {"changes": app.changes(project_id, session_id)}
                    elif parts[5] == "undo":
                        result = app.undo(project_id, session_id)
                    elif parts[5] == "report":
                        self.download(app.export_report(project_id, session_id), "task-" + session_id + ".md", "text/markdown")
                        return
                    elif parts[5] == "logs":
                        self.download(app.export_logs(project_id, session_id), "task-" + session_id + ".jsonl", "application/octet-stream")
                        return
                    else:
                        raise ValueError("Unknown session operation.")
                else:
                    raise ValueError("Unknown project operation.")
            else:
                self.send(404, {"error": "Not found."})
                return
            self.send(200, result)
        except (OSError, ValueError, KeyError) as exc:
            self.send(400, {"error": Redactor().text(str(exc))})

    def do_POST(self):
        if not self.guard(api=True):
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.send(415, {"error": "Expected application/json."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            request_path = urlsplit(self.path).path
            maximum = 30 * 1024 * 1024 if request_path.endswith("/import") else 1000000
            if not 0 < length <= maximum:
                self.send(413, {"error": "Request is empty or too large."})
                return
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("Expected an object.")
            path = urlsplit(self.path).path
            parts = path.strip("/").split("/")
            app = self.server.service
            if path == "/api/hosted-ui":
                if self.headers.get("Origin") not in self.server.origins or self.headers.get("Sec-Fetch-Site") == "cross-site":
                    self.send(403, {"error": "Approve the website from the local SPARKLE CODER app."})
                    return
                result = self.server.pair_website(body.get("url"))
            elif path == "/api/disconnect-hosted-ui":
                origin = self.headers.get("Origin")
                cors = {"Access-Control-Allow-Origin": origin, "Vary": "Origin"} if origin == self.server.hosted_origin else {}
                with self.server.pairing_lock:
                    self.server.hosted_origin = None
                    self.server.hosted_token = None
                self.send(200, {"disconnected": True}, extra_headers=cors)
                return
            elif path == "/api/settings":
                result = app.configure(body)
            elif path == "/api/experience":
                result = app.experience(body.get("experience"))
            elif path == "/api/connect":
                result = app.connect()
            elif path == "/api/projects":
                result = app.add_project(body.get("name", ""), body.get("path", ""))
            elif path == "/api/storage":
                result = app.storage(body.get("path"))
            elif path == "/api/retry-project-migration":
                result = app.retry_project_migration()
            elif path == "/api/open-folder":
                if body.get("project_id"):
                    folder = app.project(body["project_id"])[1].root
                elif body.get("target") == "projects":
                    folder = app.projects_directory
                else:
                    folder = app.directory
                if os.name == "nt":
                    os.startfile(str(folder))
                else:
                    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(folder)],
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                result = {"path": str(folder)}
            elif path == "/api/select-project":
                app.project(body["project_id"])
                with app.lock:
                    app.data["selected_project"] = body["project_id"]
                    app.save()
                result = {"selected_project": body["project_id"]}
            elif path == "/api/select-folder":
                result = choose_folder()
            elif path == "/api/demo":
                result = app.demo()
            elif path == "/api/runs":
                result = app.start(body["project_id"], body.get("goal", ""), body.get("verify"),
                                   body.get("session_id"), review_edits=body.get("review_edits", False),
                                   task_mode=body.get("task_mode"))
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] in ("import", "duplicate", "export-folder"):
                result = app.file_action(parts[2], parts[3], body)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "brief":
                result = app.project_context(parts[2], body)
            elif len(parts) == 4 and parts[:2] == ["api", "projects"] and parts[3] == "reconnect":
                result = app.reconnect_project(parts[2], body.get("path"))
            elif len(parts) == 4 and parts[:2] == ["api", "runs"]:
                job = app.job(parts[2])
                if parts[3] == "approval":
                    job.answer(body["approval_id"], body["allow"])
                elif parts[3] == "stop":
                    job.cancel()
                elif parts[3] == "pause":
                    job.pause()
                elif parts[3] == "resume":
                    job.resume()
                else:
                    raise ValueError("Unknown run action.")
                result = job.public()
            elif len(parts) == 6 and parts[:2] == ["api", "projects"] and parts[3] == "sessions" and parts[5] == "undo":
                if body.get("confirm") is not True:
                    raise ValueError("Confirm the displayed file rollback first.")
                result = app.undo(parts[2], parts[4], apply=True)
            elif path == "/api/quit":
                app.close()
                self.send(200, {"stopped": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            else:
                self.send(404, {"error": "Not found."})
                return
            self.send(200, result)
        except Exception as exc:
            # No traceback, request bodies, credentials, or provider response bodies are exposed.
            self.send(400, {"error": Redactor((self.server.service.config().api_key,)).text(str(exc))})


def main(argv=None):
    parser = argparse.ArgumentParser(description="Open SPARKLE CODER, your personal coding workspace.")
    parser.add_argument("--state-dir", type=Path, default=default_app_dir())
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--no-open", action="store_true")
    args = parser.parse_args(argv)
    directory = args.state_dir.expanduser().resolve()
    instance = directory / "instance.json"
    previous_instances = [instance]
    if directory == default_app_dir():
        previous_instances += [path / "instance.json" for path in legacy_app_dirs()]
    for previous_instance in previous_instances if not args.no_open else []:
        if not previous_instance.exists() or previous_instance.is_symlink():
            continue
        try:
            previous = json.loads(previous_instance.read_text("utf-8"))
            url = urlsplit(previous["origin"])
            if url.scheme == "http" and url.hostname == "127.0.0.1" and url.port:
                request = urllib.request.Request(previous["origin"] + "/api/state",
                    headers={"X-Sparkle-Token": previous["token"], "X-Nemotron-Token": previous["token"]})
                with urllib.request.urlopen(request, timeout=1) as response:
                    if response.status == 200:
                        running = json.loads(response.read())
                        if running.get("version") != __version__:
                            webbrowser.open(previous["origin"] + "/#token=" + previous["token"])
                            raise RuntimeError("An older SPARKLE CODER is still running. "
                                               "Use Quit app in that window, then open this updated launcher again.")
                        webbrowser.open(previous["origin"] + "/#token=" + previous["token"])
                        return 0
        except (OSError, ValueError, KeyError):
            pass
    app = AppService(directory)
    server = LocalServer(("127.0.0.1", args.port), app)
    write_json(instance, {"origin": server.origin, "token": server.token, "pid": os.getpid()})
    if not args.no_open:
        webbrowser.open(server.origin + "/#token=" + server.token)
    print("SPARKLE CODER is running. Use the app's Quit button to close it.", flush=True)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()
        try:
            if json.loads(instance.read_text("utf-8")).get("pid") == os.getpid():
                instance.unlink()
        except (OSError, ValueError):
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
