"""Test a disposable copy of a packaged app with a scripted model and real commands.

Usage: python scripts/smoke_packaged.py dist/SparkleCoder
"""
import argparse
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs, urlsplit
import zipfile


def smoke(executable):
    with tempfile.TemporaryDirectory(prefix="sparkle-executable-") as temporary:
        root = Path(temporary)
        binary = root / executable.name
        shutil.copy2(executable, binary)
        directory = root / "APP_DATA"
        runtime_temp = root / "runtime-temp"
        runtime_temp.mkdir()
        env = {**os.environ, "SPARKLE_PYTHON": sys.executable,
               "TMPDIR": str(runtime_temp), "TEMP": str(runtime_temp), "TMP": str(runtime_temp),
               "XDG_CONFIG_HOME": str(root / "unused-config"),
               "LOCALAPPDATA": str(root / "unused-local-data"),
               "NVIDIA_API_KEY": "", "LOCAL_MODEL_API_KEY": ""}
        startup_log = root / "startup.log"
        with startup_log.open("wb") as stream:
            process = subprocess.Popen([str(binary), "--no-open"], cwd=root, env=env,
                                       stdout=stream, stderr=stream)
        origin = local_token = None
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

        def request(path, body=None, *, token=None, website=None, method=None, extra=None):
            headers = {"X-Sparkle-Token": token or local_token}
            if website:
                headers.update({"Origin": website, "Sec-Fetch-Site": "cross-site"})
            if body is not None:
                headers["Content-Type"] = "application/json"
            headers.update(extra or {})
            req = urllib.request.Request(origin + path,
                data=json.dumps(body).encode() if body is not None else None,
                headers=headers, method=method)
            with opener.open(req, timeout=8) as response:
                data = response.read()
                value = json.loads(data) if "application/json" in response.headers.get("Content-Type", "") else data
                return value, response.headers

        try:
            deadline = time.monotonic() + 20
            instance = directory / "instance.json"
            while not instance.is_file() and time.monotonic() < deadline:
                if process.poll() is not None:
                    logs = [startup_log, directory / "launcher.log"]
                    detail = "\n".join(p.read_text("utf-8", errors="replace")[-3000:] for p in logs if p.is_file())
                    raise AssertionError("Packaged executable exited before serving the app: " + detail)
                time.sleep(0.1)
            record = json.loads(instance.read_text("utf-8"))
            origin, local_token = record["origin"], record["token"]
            state, _ = request("/api/state")
            assert state["version"] == "0.6.3", state["version"]
            assert (root / "PROJECTS").is_dir(), "Projects must live beside the executable"
            html, _ = request("/")
            assert b"app.js" in html
            website = "https://sparkle-smoke.example"
            pair, _ = request("/api/hosted-ui", {"url": website}, extra={"Origin": origin})
            token = parse_qs(urlsplit(pair["url"]).fragment)["token"][0]
            assert token != local_token

            def hosted(path, body=None):
                result, headers = request(path, body, token=token, website=website)
                assert headers["Access-Control-Allow-Origin"] == website
                return result

            _, headers = request("/api/demo", token=token, website=website, method="OPTIONS",
                extra={"Access-Control-Request-Method": "POST",
                       "Access-Control-Request-Headers": "content-type,x-sparkle-token",
                       "Access-Control-Request-Private-Network": "true"})
            assert headers["Access-Control-Allow-Private-Network"] == "true"
            demo = hosted("/api/demo", {})
            run_path = "/api/runs/" + demo["run"]["id"]
            approved = False
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                run = hosted(run_path)
                if run["status"] == "approval":
                    hosted(run_path + "/approval", {"approval_id": run["approval"]["id"], "allow": True})
                    approved = True
                elif run["status"] == "checked":
                    break
                elif run["status"] in {"blocked", "needs_input", "interrupted"}:
                    raise AssertionError("Packaged demo stopped: " + run["status"])
                time.sleep(0.05)
            else:
                raise AssertionError("Packaged demo did not finish")
            assert approved, "The real command must require approval"
            assert [c["ok"] for c in run["session"]["checks"]] == [False, True]
            prefix = "/api/projects/" + demo["project"]["id"]
            assert "calculator.py" in hosted(prefix + "/files")["files"]
            assert b"return a + b" in hosted(prefix + "/download?path=calculator.py")
            assert hosted(prefix + "/sessions")["sessions"][0]["id"] == run["session_id"]
            archive = hosted(prefix + "/download-project")
            with zipfile.ZipFile(io.BytesIO(archive)) as exported:
                assert "calculator.py" in exported.namelist()
                assert b"return a + b" in exported.read("calculator.py")
            hosted("/api/disconnect-hosted-ui", {})
            try:
                hosted("/api/state")
            except urllib.error.HTTPError as error:
                assert error.code == 403
                error.close()
            else:
                raise AssertionError("Disconnected website retained access")
            request("/api/state")
            request("/api/quit", {})
            assert process.wait(timeout=10) == 0
            assert not instance.exists()
            print("Packaged app passed: startup, PROJECTS, website pairing, preflight, command approval, "
                  "real repair, history, file/ZIP downloads, revocation and shutdown.")
            print("Model replies were scripted. Browser rendering and native folder dialogs were not tested.")
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("executable", type=Path)
    args = parser.parse_args()
    smoke(args.executable.resolve(strict=True))
