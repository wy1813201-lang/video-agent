import io
import os
import sys
import types
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

import gemini_cli
from src.gemini_web_client import GeminiWebClient


class GeminiFixesTest(unittest.TestCase):
    def test_save_json_result_with_filename_only(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                saved_path = gemini_cli._save_json_result("result.json", {"ok": True})
                self.assertTrue(saved_path.endswith(os.path.join(tmpdir, "result.json")))
                self.assertTrue(os.path.exists(saved_path))
            finally:
                os.chdir(old_cwd)

    def test_require_json_affects_prompt(self):
        client = GeminiWebClient()

        result_with_json = client.generate_script("写一个短剧", require_json=True)
        self.assertIn("输出JSON格式", result_with_json["prompt"])
        self.assertTrue(result_with_json["require_json"])

        result_without_json = client.generate_script("写一个短剧", require_json=False)
        self.assertEqual("写一个短剧", result_without_json["prompt"])
        self.assertFalse(result_without_json["require_json"])

    def test_cli_handles_value_error_with_specific_exit_code(self):
        fake_module = types.ModuleType("gemini_web_client")

        class BadClient:
            def generate_script(self, _prompt):
                raise ValueError("bad format")

        fake_module.GeminiWebClient = BadClient

        with patch.dict(sys.modules, {"gemini_web_client": fake_module}):
            with patch.object(sys, "argv", ["gemini_cli.py", "--prompt", "x"]):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = gemini_cli.main()

        output = buf.getvalue()
        self.assertEqual(2, rc)
        self.assertIn("格式异常", output)

    def test_cli_import_error_classified(self):
        original_import = __import__

        def raising_import(name, *args, **kwargs):
            if name == "gemini_web_client":
                raise ModuleNotFoundError("missing module")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=raising_import):
            with patch.object(sys, "argv", ["gemini_cli.py", "--prompt", "x"]):
                buf = io.StringIO()
                with redirect_stdout(buf):
                    rc = gemini_cli.main()

        output = buf.getvalue()
        self.assertEqual(1, rc)
        self.assertIn("无法导入 Gemini 客户端模块", output)


if __name__ == "__main__":
    unittest.main()
