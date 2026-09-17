import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from sparkle_coder.config import Config
from sparkle_coder.demo import python_command
from sparkle_coder.execution import CommandRunner
from sparkle_coder.workspace import Workspace


class ExecutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.workspace = Workspace(Path(self.tmp.name))
        self.runner = CommandRunner(self.workspace, Config(auto_approve=True), lambda _: True)

    def test_python_command_and_nonzero_exit_are_real(self):
        success = self.runner.run(python_command("-c", "print(6 * 7)"))
        self.assertTrue(success["ok"])
        self.assertIn("42", success["output"])
        failed = self.runner.run(python_command("-c", "raise SystemExit(7)"))
        self.assertEqual(failed["exit_code"], 7)
        self.assertFalse(failed["ok"])

    def test_timeout_stops_a_hung_process(self):
        result = self.runner.run(python_command("-c", "import time; time.sleep(20)"), timeout=1)
        self.assertTrue(result["timed_out"])
        self.assertFalse(result["ok"])
        self.assertLess(result["seconds"], 8)

    def test_model_credential_is_not_in_child_environment(self):
        with patch.dict(os.environ, {"NVIDIA_API_KEY": "do-not-send-this-to-child"}):
            result = self.runner.run(python_command("-c", "import os; print(os.environ.get('NVIDIA_API_KEY', 'MISSING'))"))
        self.assertEqual(result["output"].strip(), "MISSING")

    def test_large_command_output_is_bounded(self):
        result = self.runner.run(python_command("-c", "print('x' * 200000)"))
        self.assertTrue(result["ok"])
        self.assertLess(len(result["output"]), 49000)
        self.assertIn("truncated", result["output"])

    @unittest.skipUnless(shutil.which("node"), "Node.js not installed")
    def test_javascript_executes_through_same_language_independent_runner(self):
        (self.workspace.root / "check.js").write_text(
            "const assert = require('node:assert/strict');\n"
            "const double = x => x * 2;\nassert.equal(double(21), 42);\n"
            "console.log('JavaScript check passed');\n")
        result = self.runner.run("node check.js")
        self.assertTrue(result["ok"], result["output"])
        self.assertIn("JavaScript check passed", result["output"])

    @unittest.skipUnless(shutil.which("cc"), "C compiler not installed")
    def test_native_c_compilation_uses_the_same_runner(self):
        (self.workspace.root / "main.c").write_text(
            "#include <stdio.h>\nint main(void) { puts(\"C check passed\"); return 0; }\n")
        result = self.runner.run("cc main.c -o program && ./program")
        self.assertTrue(result["ok"], result["output"])
        self.assertIn("C check passed", result["output"])
