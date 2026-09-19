"""Exercise actual process death, exclusive recovery, and nonfatal migration."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.request
from unittest.mock import Mock, patch

from sparkle_coder.locking import process_running
from sparkle_coder.state import Session
from sparkle_coder.webapp import AppService
from sparkle_coder.workspace import Workspace, WorkspaceError
import test_project_recovery
import test_web


class LockRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.workspace = Workspace(Path(temporary.name) / "project")
        self.marker = self.workspace.state_dir / "workspace.lock"
        self.root = Path(__file__).resolve().parent.parent

    def departed_pid(self):
        child = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                               capture_output=True, text=True, timeout=5)
        self.assertEqual(child.returncode, 0, child.stderr)
        pid = int(child.stdout)
        self.assertIs(process_running(pid), False)
        return pid

    def child(self, code):
        child = subprocess.Popen([sys.executable, "-c", code, str(self.workspace.root)],
                                 cwd=self.root, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        def cleanup():
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)
        self.addCleanup(cleanup)
        return child

    def line(self, child):
        result = queue.Queue()
        reader = threading.Thread(target=lambda: result.put(child.stdout.readline().strip()), daemon=True)
        reader.start()
        value = result.get(timeout=5)
        reader.join(1)
        return value

    def test_legacy_dead_pid_is_recovered_and_live_pid_is_preserved(self):
        self.marker.write_text(str(self.departed_pid()))
        with self.workspace.lock() as status:
            self.assertTrue(status["recovered"])
            self.assertEqual(self.marker.read_text(), str(os.getpid()))
        self.assertFalse(self.marker.exists())
        original = str(os.getpid())
        self.marker.write_text(original)
        with self.assertRaisesRegex(WorkspaceError, "running app"):
            with self.workspace.lock():
                self.fail("Live legacy lock was taken")
        self.assertEqual(self.marker.read_text(), original)

    def test_crashed_process_releases_native_guard_and_recovers_on_next_run(self):
        (self.workspace.root / "work.txt").write_text("Keep this work")
        child = self.child("""
from pathlib import Path
import sys
from sparkle_coder.workspace import Workspace
with Workspace(Path(sys.argv[1]), create=False).lock():
    print('ready', flush=True)
    sys.stdin.readline()
""")
        self.assertEqual(self.line(child), "ready")
        self.assertEqual(self.marker.read_text(), str(child.pid))
        with self.assertRaises(WorkspaceError):
            with self.workspace.lock():
                self.fail("A live task lost its workspace")
        child.kill()
        child.communicate(timeout=5)
        self.assertTrue(self.marker.exists())
        with self.workspace.lock() as result:
            self.assertTrue(result["recovered"])
            self.assertEqual((self.workspace.root / "work.txt").read_text(), "Keep this work")
        self.assertFalse(self.marker.exists())
        with self.workspace.lock() as result:
            self.assertFalse(result["recovered"])

    def test_two_processes_cannot_both_recover_the_same_stale_lock(self):
        self.marker.write_text(str(self.departed_pid()))
        code = """
from pathlib import Path
import sys
from sparkle_coder.workspace import Workspace, WorkspaceError
workspace = Workspace(Path(sys.argv[1]), create=False)
print('ready', flush=True)
sys.stdin.readline()
try:
    with workspace.lock():
        print('acquired', flush=True)
        sys.stdin.readline()
except WorkspaceError:
    print('busy', flush=True)
"""
        children = [self.child(code), self.child(code)]
        for child in children:
            self.assertEqual(self.line(child), "ready")
        for child in children:
            child.stdin.write("go\n")
            child.stdin.flush()
        results = [self.line(child) for child in children]
        self.assertEqual(sorted(results), ["acquired", "busy"])
        winner = children[results.index("acquired")]
        self.assertEqual(self.marker.read_text(), str(winner.pid))
        winner.communicate("done\n", timeout=5)
        self.assertEqual(winner.returncode, 0)
        self.assertFalse(self.marker.exists())

    def test_unknown_or_malformed_owners_are_never_guessed_stale(self):
        for value in ("", "not a pid", "0", "-1", "9" * 70):
            with self.subTest(value=value):
                self.marker.write_text(value)
                with self.assertRaises(WorkspaceError):
                    with self.workspace.lock():
                        self.fail("Invalid lock was reclaimed")
                self.assertEqual(self.marker.read_text(), value)
        self.marker.write_text("12345")
        with patch("sparkle_coder.locking.process_running", return_value=None):
            with self.assertRaisesRegex(WorkspaceError, "could not confirm"):
                with self.workspace.lock():
                    self.fail("Unknown owner was reclaimed")
        self.assertEqual(self.marker.read_text(), "12345")

    def test_linked_lock_files_and_guards_do_not_change_their_targets(self):
        outside = self.workspace.root.parent / "outside"
        outside.write_text(str(self.departed_pid()))
        original = outside.read_bytes()
        for target in (self.marker, self.workspace.state_dir / "workspace.guard"):
            with self.subTest(target=target):
                target.unlink(missing_ok=True)
                target.symlink_to(outside)
                with self.assertRaises(WorkspaceError):
                    with self.workspace.lock():
                        self.fail("Linked lock was used")
                self.assertTrue(target.is_symlink())
                self.assertEqual(outside.read_bytes(), original)
                target.unlink()
        os.link(outside, self.marker)
        with self.assertRaises(WorkspaceError):
            with self.workspace.lock():
                self.fail("Hard-linked marker was used")
        self.assertEqual(outside.read_bytes(), original)

    def test_cleanup_does_not_delete_a_replaced_marker(self):
        with self.workspace.lock():
            self.marker.unlink()
            self.marker.write_text("Replacement lock")
        self.assertEqual(self.marker.read_text(), "Replacement lock")

    def test_permission_error_is_unknown_and_invalid_pids_are_never_signalled(self):
        with patch("sparkle_coder.locking.os.kill", side_effect=PermissionError) as probe:
            self.assertIsNone(process_running(123))
            self.assertEqual(probe.call_args.args, (123, 0))
        with patch("sparkle_coder.locking.os.kill") as probe:
            for pid in (-1, 0, True, None, 2**80):
                self.assertIsNone(process_running(pid))
            probe.assert_not_called()

    def test_windows_probe_uses_query_handles_and_never_os_kill(self):
        import ctypes.wintypes  # Load before simulating the OS branch.
        kernel = Mock()
        with patch("sparkle_coder.locking.os.name", "nt"), patch("ctypes.WinDLL", create=True, return_value=kernel), \
                patch("ctypes.get_last_error", create=True, return_value=87) as error, \
                patch("sparkle_coder.locking.os.kill") as signal:
            kernel.OpenProcess.return_value = 101
            for status, expected in ((0, False), (258, True), (0xffffffff, None)):
                kernel.WaitForSingleObject.return_value = status
                self.assertIs(process_running(123), expected)
                kernel.CloseHandle.assert_called_with(101)
            kernel.OpenProcess.assert_called_with(0x00100000, False, 123)
            kernel.OpenProcess.return_value = None
            self.assertIs(process_running(123), False)
            error.return_value = 5  # Access denied is not a dead process.
            self.assertIsNone(process_running(123))
            signal.assert_not_called()


class MigrationLockTests(unittest.TestCase):
    setUp = test_project_recovery.ProjectRecoveryTests.setUp
    open_app = test_project_recovery.ProjectRecoveryTests.open_app
    save_old = test_project_recovery.ProjectRecoveryTests.save_old

    def old_project(self):
        workspace = Workspace(Path(self.missing["path"]))
        (workspace.root / "work.txt").write_text("Original saved work")
        session = Session.create(workspace, "Resume saved work", [], {})
        original = self.save_old()
        return workspace, session, original

    def test_stale_lock_migrates_with_history_and_no_copied_runtime_locks(self):
        workspace, session, original = self.old_project()
        pid = int(subprocess.check_output([sys.executable, "-c", "import os; print(os.getpid())"], text=True))
        (workspace.state_dir / "workspace.lock").write_text(str(pid))
        app = self.open_app()
        new = app.project(self.missing["id"])[1]
        self.assertEqual(new.read("work.txt")[0], "Original saved work")
        self.assertEqual(Session.load(new, session.id).state["goal"], "Resume saved work")
        self.assertEqual(app.data["storage_migration"]["recovered_locks"], 1)
        self.assertFalse((new.state_dir / "workspace.lock").exists())
        self.assertFalse((new.state_dir / "workspace.guard").exists())
        self.assertFalse((workspace.state_dir / "workspace.lock").exists())
        self.assertEqual((self.legacy / "settings.json").read_bytes(), original)

    def test_busy_project_does_not_block_startup_and_retry_after_exit_preserves_history(self):
        workspace, session, original = self.old_project()
        marker = workspace.state_dir / "workspace.lock"
        with workspace.lock():
            before = marker.read_bytes()
            app = self.open_app()
            waiting = next(p for p in app.state()["projects"] if p["id"] == self.missing["id"])
            self.assertTrue(waiting["migration_pending"])
            self.assertFalse(waiting["available"])
            self.assertEqual(waiting["path"], str(workspace.root))
            self.assertNotEqual(app.data["selected_project"], waiting["id"])
            self.assertEqual(app.history(app.data["selected_project"]), [])
            self.assertEqual(app.retry_project_migration()["pending"], 1)
            self.assertEqual(marker.read_bytes(), before)
            reopened = self.open_app()
            self.assertEqual(reopened.data["projects"], app.data["projects"])
            with self.assertRaisesRegex(ValueError, "Retry project move"):
                app.project(waiting["id"])
        result = app.retry_project_migration()
        self.assertEqual((result["copied"], result["pending"]), (1, 0))
        new = app.project(self.missing["id"])[1]
        self.assertEqual(new.root.parent, app.projects_directory)
        self.assertEqual(Session.load(new, session.id).state["goal"], "Resume saved work")
        self.assertEqual((workspace.root / "work.txt").read_text(), "Original saved work")
        self.assertEqual((self.legacy / "settings.json").read_bytes(), original)
        self.assertEqual(app.retry_project_migration()["copied"], 0)

    def test_uncertain_lock_and_linked_history_stay_deferred_without_stopping_app(self):
        workspace, _, _ = self.old_project()
        marker = workspace.state_dir / "workspace.lock"
        marker.write_text("unreadable owner")
        app = self.open_app()
        self.assertEqual(app.retry_project_migration()["pending"], 1)
        self.assertEqual(marker.read_text(), "unreadable owner")
        marker.unlink()  # Test fixture repair; production never guesses an unknown owner.
        saved = workspace.root / "saved-history"
        workspace.state_dir.rename(saved)
        workspace.state_dir.symlink_to(saved, target_is_directory=True)
        self.assertEqual(app.retry_project_migration()["pending"], 1)
        record = next(p for p in app.data["projects"] if p["id"] == self.missing["id"])
        self.assertIn("points to another location", record["migration_pending"])
        self.assertTrue(workspace.state_dir.is_symlink())
        workspace.state_dir.unlink()
        saved.rename(workspace.state_dir)
        self.assertEqual(app.retry_project_migration()["pending"], 0)

    def test_source_stays_locked_through_copy_and_failed_retry_preserves_settings(self):
        workspace, _, _ = self.old_project()
        with workspace.lock():
            app = self.open_app()
        before = app.settings_path.read_bytes()
        import shutil
        original_copy = shutil.copytree
        observed = []
        def copy(source, target, *args, **kwargs):
            if Path(source) == workspace.root:
                with self.assertRaises(WorkspaceError):
                    with workspace.lock():
                        self.fail("Source was not locked while copying")
                observed.append(True)
                raise OSError("disk full")
            return original_copy(source, target, *args, **kwargs)
        with patch("sparkle_coder.storage.shutil.copytree", side_effect=copy):
            with self.assertRaisesRegex(OSError, "disk full"):
                app.retry_project_migration()
        self.assertEqual(observed, [True])
        self.assertEqual(app.settings_path.read_bytes(), before)
        self.assertEqual(app.data, json.loads(before))
        self.assertEqual((workspace.root / "work.txt").read_text(), "Original saved work")
        self.assertFalse((workspace.state_dir / "workspace.lock").exists())
        self.assertEqual(app.retry_project_migration()["copied"], 1)

    def test_storage_relocation_recovers_stale_locks_and_does_not_copy_them(self):
        app = self.open_app()
        identity = app.data["selected_project"]
        workspace = app.project(identity)[1]
        pid = int(subprocess.check_output([sys.executable, "-c", "import os; print(os.getpid())"], text=True))
        (workspace.state_dir / "workspace.lock").write_text(str(pid))
        app.storage(str(self.root / "new-storage"))
        moved = app.project(identity)[1]
        self.assertFalse((moved.state_dir / "workspace.lock").exists())
        self.assertFalse((moved.state_dir / "workspace.guard").exists())
        with moved.lock():
            pass

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux source-launcher reproduction")
    def test_linux_source_launcher_opens_with_the_reported_legacy_lock_condition(self):
        import shutil
        workspace, session, _ = self.old_project()
        pid = int(subprocess.check_output([sys.executable, "-c", "import os; print(os.getpid())"], text=True))
        (workspace.state_dir / "workspace.lock").write_text(str(pid))
        source = Path(__file__).resolve().parent.parent
        shutil.copytree(source / "sparkle_coder", self.application / "sparkle_coder",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copy2(source / "Open_SPARKLE_CODER.pyw", self.application)
        # The real launcher uses default portable paths and legacy discovery.
        # --no-open prevents opening a browser on the test machine.
        child = subprocess.Popen([sys.executable, "Open_SPARKLE_CODER.pyw", "--no-open"],
                                 cwd=self.application, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 env={**os.environ, "XDG_CONFIG_HOME": str(self.legacy.parent), "BROWSER": "true"})
        instance = self.application / "APP_DATA" / "instance.json"
        try:
            deadline = time.monotonic() + 8
            while not instance.exists() and child.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            log = self.application / "APP_DATA" / "launcher.log"
            self.assertTrue(instance.exists(), log.read_text() if log.exists() else "Launcher did not start")
            connection = json.loads(instance.read_text())
            headers = {"X-Sparkle-Token": connection["token"]}
            request = urllib.request.Request(connection["origin"] + "/api/state", headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                state = json.load(response)
            self.assertEqual(state["selected_project"], self.missing["id"])
            self.assertEqual(state["storage"]["migration"]["recovered_locks"], 1)
            request = urllib.request.Request(connection["origin"] + f'/api/projects/{self.missing["id"]}/sessions', headers=headers)
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertEqual(json.load(response)["sessions"][0]["id"], session.id)
            request = urllib.request.Request(connection["origin"] + "/api/quit", data=b"{}",
                                             headers={**headers, "Content-Type": "application/json"})
            with urllib.request.urlopen(request, timeout=5) as response:
                self.assertTrue(json.load(response)["stopped"])
            _, errors = child.communicate(timeout=5)
            self.assertEqual(child.returncode, 0, errors.decode())
        finally:
            if child.poll() is None:
                child.kill()
            child.communicate(timeout=5)


class MigrationRetryWebTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api

    def test_retry_route_is_authenticated_and_does_not_move_during_an_active_task(self):
        route = "/api/retry-project-migration"
        self.assertEqual(self.request(route, {}, auth=False)[0], 401)
        self.assertEqual(self.request(route, {}, headers={"Origin": "https://example.com"})[0], 403)
        with patch.object(self.app, "active", return_value=object()):
            status, body, _ = self.request(route, {})
            self.assertEqual(status, 400)
            self.assertIn("active task", body["error"])
        self.assertEqual(self.api(route, {})["pending"], 0)
