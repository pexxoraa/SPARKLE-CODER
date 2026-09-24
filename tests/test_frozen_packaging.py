"""application_root() must resolve next to the real executable when running
as a PyInstaller-frozen app, not inside the temporary extraction directory
__file__ would otherwise point to (which is deleted when the app closes)."""
import sys
import json
import os
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from sparkle_coder.webapp import application_root
from sparkle_coder.checks import discover_checks
from sparkle_coder.demo import run_demo
from sparkle_coder.diagnostics import inspect_setup
from sparkle_coder.config import Config
from sparkle_coder.picker import choose_folder, run_picker
from sparkle_coder.python_runtime import python_argv, python_command
from sparkle_coder.workspace import Workspace


class ApplicationRootTests(unittest.TestCase):
    def test_normal_run_uses_the_source_tree(self):
        with patch.object(sys, "frozen", False, create=True):
            root = application_root()
        # Two levels up from sparkle_coder/webapp.py is the project root.
        self.assertTrue((root / "sparkle_coder" / "webapp.py").exists())

    def test_frozen_run_uses_the_executable_directory(self):
        fake_exe = "/opt/testers/SparkleCoder/SparkleCoder.exe"
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", fake_exe):
            root = application_root()
        self.assertEqual(root, Path(fake_exe).resolve().parent)
        # Specifically NOT wherever __file__ happens to live (e.g. a
        # PyInstaller temp extraction dir), which is the bug this guards.
        self.assertNotEqual(root, Path(__file__).resolve().parent)


class FrozenExecutionTests(unittest.TestCase):
    def test_frozen_demo_uses_external_python_and_completes_real_checks(self):
        interpreter = sys.executable
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "executable", str(Path(temporary) / "SparkleCoder.exe")), \
             patch.dict(os.environ, {"SPARKLE_PYTHON": interpreter}):
            self.assertEqual(run_demo(Path(temporary) / "demo", emit=lambda *_: None), 0)
            checks = discover_checks(Workspace(Path(temporary) / "demo"))["checks"]
            self.assertTrue(checks)
            self.assertNotIn("SparkleCoder.exe", checks[0]["command"])
            result = subprocess.run(checks[0]["command"], shell=True, cwd=Path(temporary) / "demo",
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_missing_external_python_is_reported_instead_of_the_app(self):
        with tempfile.TemporaryDirectory() as temporary, \
             patch.object(sys, "frozen", True, create=True), \
             patch.dict(os.environ, {"SPARKLE_PYTHON": ""}), \
             patch("sparkle_coder.python_runtime.shutil.which", return_value=None):
            workspace = Workspace(Path(temporary))
            (workspace.root / "requirements.txt").touch()
            self.assertIsNone(python_argv(workspace.root))
            with self.assertRaisesRegex(ValueError, "Python for running project code"):
                python_command("-c", "print(42)")
            setup = inspect_setup(workspace, Config())
            python = next(item for item in setup["items"] if item["id"] == "tool:__python__")
            self.assertEqual(python["status"], "attention")

    def test_project_environment_takes_precedence(self):
        with tempfile.TemporaryDirectory() as temporary:
            executable = Path(temporary) / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            executable.parent.mkdir(parents=True)
            executable.write_text("project interpreter")
            executable.chmod(0o755)
            self.assertEqual(python_argv(Path(temporary)), [str(executable)])

    def test_picker_roundtrip_does_not_use_stdout(self):
        window = SimpleNamespace(withdraw=lambda: None, attributes=lambda *_: None, destroy=lambda: None)
        chooser = SimpleNamespace(askdirectory=lambda **_: "/chosen/project")
        tkinter = SimpleNamespace(Tk=lambda: window, filedialog=chooser)
        helper_calls = []
        def helper(argv, **options):
            helper_calls.append(argv)
            self.assertEqual(options["stdout"], subprocess.DEVNULL)
            run_picker(argv[-1])
            return subprocess.CompletedProcess(argv, 0)
        with patch.object(sys, "frozen", True, create=True), patch.object(sys, "stdout", None), \
             patch.dict(sys.modules, {"tkinter": tkinter}), \
             patch("sparkle_coder.picker.subprocess.run", side_effect=helper):
            result = choose_folder()
        self.assertEqual(result, {"path": "/chosen/project"})
        self.assertEqual(helper_calls[0][1], "--sparkle-picker")
        self.assertFalse(Path(helper_calls[0][-1]).exists(), "Picker temp file should be cleaned up")

    def test_picker_cancel_and_failed_helper_have_distinct_results(self):
        def cancelled(argv, **_):
            Path(argv[-1]).write_text(json.dumps({"path": ""}))
            return subprocess.CompletedProcess(argv, 0)
        with patch("sparkle_coder.picker.subprocess.run", side_effect=cancelled):
            self.assertEqual(choose_folder(), {"path": ""})
        with patch("sparkle_coder.picker.subprocess.run", side_effect=OSError("No GUI")):
            self.assertIn("Paste", choose_folder()["error"])


if __name__ == "__main__":
    unittest.main()
