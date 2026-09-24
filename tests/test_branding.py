import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.webapp import AppService, default_app_dir


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux storage-location selection")
class StorageCompatibilityTests(unittest.TestCase):
    def test_legacy_default_run_caps_are_migrated_to_unlimited(self):
        with tempfile.TemporaryDirectory() as folder:
            app_dir = Path(folder) / "nemotron-workspace"
            app_dir.mkdir()
            (app_dir / "settings.json").write_text(json.dumps({
                "settings": {"max_steps": 40, "max_seconds": 1800,
                              "max_total_tokens": 250000},
                "projects": [], "selected_project": None}))
            app = AppService(app_dir)
            self.assertIsNone(app.config().max_steps)
            self.assertIsNone(app.config().max_seconds)
            self.assertIsNone(app.config().max_total_tokens)
            self.assertEqual(app.data["settings_version"], 4)
            app.close()

    def test_rename_reuses_existing_project_data(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            legacy = parent / "nemotron-workspace"
            original = AppService(legacy)
            project_id = original.data["selected_project"]
            workspace = original.project(project_id)[1]
            (workspace.root / "existing.txt").write_text("Preserve my work")
            original.close()
            app_root = parent / "SPARKLE-CODER"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(parent)}), \
                    patch("sparkle_coder.webapp.application_root", return_value=app_root):
                self.assertEqual(default_app_dir(), app_root / "APP_DATA")
                reopened = AppService(default_app_dir())
                self.assertEqual(reopened.project(project_id)[1].read("existing.txt")[0], "Preserve my work")
                self.assertEqual(reopened.project(project_id)[1].root.parent, app_root / "PROJECTS")
                self.assertEqual((workspace.root / "existing.txt").read_text(), "Preserve my work")
                reopened.close()

    def test_new_install_name_and_existing_new_location_take_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            app_root = parent / "SPARKLE-CODER"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(parent)}), \
                    patch("sparkle_coder.webapp.application_root", return_value=app_root):
                self.assertEqual(default_app_dir(), app_root / "APP_DATA")
                current = AppService(default_app_dir())
                project_id = current.data["selected_project"]
                current.close()
                legacy = parent / "nemotron-workspace"
                legacy.mkdir()
                (legacy / "settings.json").write_text("invalid older settings should not replace current data")
                reopened = AppService(default_app_dir())
                self.assertEqual(reopened.data["selected_project"], project_id)
                self.assertEqual(reopened.projects_directory, app_root / "PROJECTS")
                reopened.close()
