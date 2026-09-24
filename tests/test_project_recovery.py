"""Missing registrations must not block startup or masquerade as recovered files."""

import json
import shutil
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.state import Session
from sparkle_coder.webapp import AppService, default_app_dir
from sparkle_coder.workspace import Workspace, write_json
import test_web


class ProjectRecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.application = self.root / "SPARKLE-CODER"
        self.legacy = self.root / ".config" / "nemotron-workspace"
        for target, value in (("application_root", self.application),
                              ("legacy_app_dirs", (self.legacy, self.root / "other-config"))):
            override = patch("sparkle_coder.webapp." + target, return_value=value)
            override.start()
            self.addCleanup(override.stop)
        self.missing = {"id": "123456abcdef", "name": "My project",
                        "path": str(self.legacy / "Projects" / "my-project"), "created": "saved"}

    def open_app(self):
        app = AppService(default_app_dir())
        self.addCleanup(app.close)
        return app

    def save_old(self, projects=None, selected=None):
        write_json(self.legacy / "settings.json", {
            "projects": projects or [self.missing],
            "selected_project": selected or self.missing["id"],
            "settings": {"max_steps": 40},
        })
        return (self.legacy / "settings.json").read_bytes()

    def test_screenshot_missing_legacy_default_opens_without_recreating_it(self):
        original = self.save_old()
        app = self.open_app()
        public = app.state()
        missing = next(p for p in public["projects"] if p["id"] == self.missing["id"])
        self.assertEqual({k: missing[k] for k in self.missing}, self.missing)
        self.assertFalse(missing["available"])
        self.assertFalse(Path(missing["path"]).exists())
        self.assertNotEqual(public["selected_project"], missing["id"])
        selected, workspace = app.project(public["selected_project"])
        self.assertEqual(workspace.root.parent, self.application / "PROJECTS")
        self.assertEqual(app.history(selected["id"]), [])
        self.assertIn("Find folder", public["storage"]["migration"]["message"])
        self.assertEqual((self.legacy / "settings.json").read_bytes(), original)
        again = self.open_app()
        self.assertEqual(again.data["projects"], app.data["projects"])
        self.assertEqual(again.data["selected_project"], selected["id"])

    def test_copied_app_uses_its_own_projects_and_keeps_original_files(self):
        app = self.open_app()
        project, workspace = app.project(app.data["selected_project"])
        (workspace.root / "keep.txt").write_text("My saved code")
        session = Session.create(workspace, "Keep my history", [], {})
        copied = self.root / "moved-app"
        shutil.copytree(self.application, copied)
        with patch("sparkle_coder.webapp.application_root", return_value=copied):
            restored = self.open_app()
        new_workspace = restored.project(project["id"])[1]
        self.assertEqual(new_workspace.root, copied / "PROJECTS" / "my-project")
        self.assertEqual(new_workspace.read("keep.txt")[0], "My saved code")
        self.assertEqual(Session.load(new_workspace, session.id).state["goal"], "Keep my history")
        self.assertTrue(workspace.root.exists())
        self.assertEqual(restored.projects_directory, copied / "PROJECTS")

    def test_foreign_machine_path_never_gets_created_on_startup(self):
        forbidden = self.root / "other-machine" / "SPARKLE" / "PROJECTS"
        missing = {"id": "foreign", "name": "Keep registration", "path": str(forbidden / "lost")}
        write_json(default_app_dir() / "settings.json", {"projects_path": str(forbidden), "projects": [missing]})
        original_mkdir = Path.mkdir
        def mkdir(path, *args, **kwargs):
            if path == forbidden or forbidden in path.parents:
                raise PermissionError("Other machine")
            return original_mkdir(path, *args, **kwargs)
        with patch.object(Path, "mkdir", mkdir):
            app = self.open_app()
        self.assertEqual(app.projects_directory, self.application / "PROJECTS")
        self.assertEqual(next(p for p in app.data["projects"] if p["id"] == "foreign")["path"], missing["path"])
        self.assertFalse(forbidden.exists())
        self.assertNotEqual(app.data["selected_project"], "foreign")

    def test_windows_paths_reconnect_when_copied_to_another_os(self):
        target = self.application / "PROJECTS" / "existing"
        target.mkdir(parents=True)
        (target / "keep.txt").write_text("Actual saved work")
        write_json(default_app_dir() / "settings.json", {"projects_path": r"C:\Users\Tester\SPARKLE\PROJECTS",
                   "projects": [{"id": "crossos", "name": "Existing", "path": r"C:\Users\Tester\SPARKLE\PROJECTS\existing"}]})
        app = self.open_app()
        self.assertEqual(app.project("crossos")[1].root, target)

    def test_missing_entry_does_not_stop_other_projects_and_history_migrating(self):
        good = Workspace(self.legacy / "Projects" / "good")
        (good.root / "keep.txt").write_text("Saved work")
        session = Session.create(good, "Saved task", [], {})
        good_entry = {"id": "good", "name": "Good", "path": str(good.root)}
        external = {"id": "external", "name": "Disconnected drive", "path": str(self.root / "drive" / "project")}
        original = self.save_old([self.missing, good_entry, external])
        app = self.open_app()
        self.assertEqual(app.data["selected_project"], "good")
        moved = app.project("good")[1]
        self.assertEqual(moved.read("keep.txt")[0], "Saved work")
        self.assertEqual(moved.root.parent, self.application / "PROJECTS")
        self.assertEqual(Session.load(moved, session.id).state["goal"], "Saved task")
        self.assertEqual((good.root / "keep.txt").read_text(), "Saved work")
        self.assertFalse(next(p for p in app.state()["projects"] if p["id"] == "external")["available"])
        self.assertEqual((self.legacy / "settings.json").read_bytes(), original)

    def test_missing_current_project_is_not_recreated_by_open_or_add(self):
        app = self.open_app()
        project, workspace = app.project(app.data["selected_project"])
        moved = self.root / "moved-project"
        workspace.root.rename(moved)
        for call in (lambda: app.project(project["id"]), lambda: app.add_project("Again", project["path"])):
            with self.assertRaisesRegex(ValueError, "Find folder"):
                call()
            self.assertFalse(workspace.root.exists())
        reopened = self.open_app()
        self.assertNotEqual(reopened.data["selected_project"], project["id"])
        self.assertFalse(workspace.root.exists())
        self.assertFalse(next(p for p in reopened.state()["projects"] if p["id"] == project["id"])["available"])

    def test_reconnecting_moved_project_keeps_identity_files_and_task_history(self):
        app = self.open_app()
        project, workspace = app.project(app.data["selected_project"])
        identity, original = project["id"], project["path"]
        (workspace.root / "work.txt").write_text("Keep this")
        session = Session.create(workspace, "Continue my task", [], {})
        session.state["verification_fingerprint"] = workspace.fingerprint()
        session.save()
        restored = self.root / "found-project"
        workspace.root.rename(restored)
        result = app.reconnect_project(identity, str(restored))
        self.assertEqual(result["id"], identity)
        self.assertEqual(result["previous_paths"], [original])
        self.assertTrue(result["available"])
        self.assertFalse(workspace.root.exists())
        reopened = self.open_app()
        self.assertEqual(reopened.data["selected_project"], identity)
        current = reopened.project(identity)[1]
        self.assertEqual(current.read("work.txt")[0], "Keep this")
        loaded = Session.load(current, session.id)
        self.assertEqual(loaded.state["goal"], "Continue my task")
        self.assertIsNone(loaded.state["verification_fingerprint"])
        self.assertIn(original, loaded.state["previous_workspaces"])
        self.assertEqual(reopened.history(identity)[0]["id"], session.id)

    def test_reconnect_requires_existing_folder_and_preserves_registration_on_failure(self):
        self.save_old()
        app = self.open_app()
        identity = self.missing["id"]
        not_folder = self.root / "file.txt"
        not_folder.write_text("A file, not a folder")
        before = app.settings_path.read_bytes()
        for path in ("", "relative/folder", str(self.root / "nonexistent"), str(not_folder),
                     app.project(app.data["selected_project"])[0]["path"]):
            with self.subTest(path=path), self.assertRaises(ValueError):
                app.reconnect_project(identity, path)
            self.assertEqual(app.settings_path.read_bytes(), before)
        self.assertFalse((self.root / "nonexistent").exists())
        found = Workspace(self.root / "found")
        with found.lock(), self.assertRaisesRegex(ValueError, "locked"):
            app.reconnect_project(identity, str(found.root))
        with patch.object(app, "active", return_value=object()), self.assertRaisesRegex(ValueError, "active task"):
            app.reconnect_project(identity, str(found.root))
        with patch.object(app, "save", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                app.reconnect_project(identity, str(found.root))
        self.assertEqual(app.settings_path.read_bytes(), before)
        self.assertEqual(app.data, json.loads(before))

    def test_restoring_original_folder_updates_availability_without_new_registration(self):
        self.save_old()
        app = self.open_app()
        original = Path(self.missing["path"])
        original.mkdir(parents=True)
        (original / "saved.txt").write_text("Restored backup")
        self.assertTrue(next(p for p in app.state()["projects"] if p["id"] == self.missing["id"])["available"])
        app.reconnect_project(self.missing["id"], str(original))
        self.assertEqual(app.data["selected_project"], self.missing["id"])
        self.assertEqual(app.project(self.missing["id"])[1].read("saved.txt")[0], "Restored backup")

    def test_storage_move_keeps_missing_paths_and_copies_available_work(self):
        app = self.open_app()
        missing, missing_workspace = app.project(app.data["selected_project"])
        missing_workspace.root.rename(self.root / "disconnected")
        good = app.add_project("Good")
        (Path(good["path"]) / "work.txt").write_text("Move me")
        original_missing = missing["path"]
        target = self.root / "new-storage"
        app.storage(str(target))
        self.assertEqual(next(p for p in app.data["projects"] if p["id"] == missing["id"])["path"], original_missing)
        self.assertFalse((target / "PROJECTS" / Path(original_missing).name).exists())
        self.assertEqual(app.project(good["id"])[1].read("work.txt")[0], "Move me")
        reopened = self.open_app()
        self.assertFalse(next(p for p in reopened.state()["projects"] if p["id"] == missing["id"])["available"])

    def test_missing_entry_does_not_hide_real_copy_failure(self):
        good = Workspace(self.legacy / "Projects" / "good")
        (good.root / "work.txt").write_text("Keep me")
        original = self.save_old([self.missing, {"id": "good", "name": "Good", "path": str(good.root)}])
        with patch("sparkle_coder.storage.shutil.copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(ValueError, "disk full"):
                self.open_app()
        self.assertFalse((default_app_dir() / "settings.json").exists())
        self.assertEqual((self.legacy / "settings.json").read_bytes(), original)
        self.assertEqual((good.root / "work.txt").read_text(), "Keep me")
        self.assertEqual(self.open_app().project("good")[1].read("work.txt")[0], "Keep me")


class ProjectRecoveryWebTests(unittest.TestCase):
    setUp = test_web.WebTests.setUp
    close = test_web.WebTests.close
    request = test_web.WebTests.request
    api = test_web.WebTests.api

    def test_recovery_http_workflow_and_authentication(self):
        identity = self.app.data["selected_project"]
        workspace = self.app.project(identity)[1]
        (workspace.root / "saved.txt").write_text("Recovered over HTTP")
        session = Session.create(workspace, "Saved task", [], {})
        restored = Path(self.tmp.name) / "found-project"
        workspace.root.rename(restored)
        self.app.close()
        self.app = AppService(Path(self.tmp.name), provider_factory=test_web.FakeProvider)
        self.server.service = self.app
        state = self.api("/api/state")
        self.assertNotEqual(state["selected_project"], identity)
        current = state["selected_project"]
        self.assertEqual(self.api(f"/api/projects/{current}/files")["files"], [])
        self.assertEqual(self.api(f"/api/projects/{current}/sessions")["sessions"], [])
        code, failed, _ = self.request(f"/api/projects/{identity}/files")
        self.assertEqual(code, 400)
        self.assertIn("Find folder", failed["error"])
        self.assertFalse(workspace.root.exists())
        route, body = f"/api/projects/{identity}/reconnect", {"path": str(restored)}
        self.assertEqual(self.request(route, body, auth=False)[0], 401)
        self.assertEqual(self.request(route, body, headers={"Origin": "https://example.com"})[0], 403)
        result = self.api(route, body)
        self.assertEqual(result["id"], identity)
        self.assertEqual(self.api("/api/state")["selected_project"], identity)
        self.assertIn("saved.txt", self.api(f"/api/projects/{identity}/files")["files"])
        self.assertEqual(self.api(f"/api/projects/{identity}/sessions")["sessions"][0]["id"], session.id)
