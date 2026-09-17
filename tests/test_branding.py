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
    def test_rename_reuses_existing_project_data(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            legacy = parent / "nemotron-workspace"
            original = AppService(legacy)
            project_id = original.data["selected_project"]
            workspace = original.project(project_id)[1]
            (workspace.root / "existing.txt").write_text("Preserve my work")
            original.close()
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(parent)}):
                self.assertEqual(default_app_dir(), legacy)
                reopened = AppService(default_app_dir())
                self.assertEqual(reopened.project(project_id)[1].read("existing.txt")[0], "Preserve my work")
                reopened.close()

    def test_new_install_name_and_existing_new_location_take_precedence(self):
        with tempfile.TemporaryDirectory() as folder:
            parent = Path(folder)
            current, legacy = parent / "sparkle-coder", parent / "nemotron-workspace"
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": str(parent)}):
                self.assertEqual(default_app_dir(), current)
                legacy.mkdir()
                (legacy / "storage-location.json").write_text(json.dumps({"path": "old-device-folder"}))
                self.assertEqual(default_app_dir(), legacy)
                current.mkdir()
                (current / "settings.json").write_text("{}")
                self.assertEqual(default_app_dir(), current)
