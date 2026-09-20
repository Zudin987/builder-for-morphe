"""Regression coverage for the CI app-update watcher's stdout contract."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.core.network import NetworkError

WATCHER_PATH = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "check_app_updates.py"
_spec = importlib.util.spec_from_file_location("check_app_updates_stdout", WATCHER_PATH)
assert _spec and _spec.loader
watcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(watcher)


class WatcherStdoutTests(unittest.TestCase):
    def test_release_api_outage_emits_valid_empty_json_on_stdout(self):
        entry = SimpleNamespace(
            enabled=True,
            table="Example",
            version="auto",
            dl_urls={"apkmirror": "https://example.invalid/app"},
            patches={"github:example/patches": {"version": "latest", "include": [], "exclude": []}},
        )
        stdout = io.StringIO()
        stderr = io.StringIO()
        with tempfile.TemporaryDirectory() as temp_dir, \
            patch.dict(os.environ, {"GITHUB_REPOSITORY": "example/builder"}), \
            patch.object(watcher, "load_toml", return_value={}), \
            patch.object(watcher, "parse_config", return_value=object()), \
            patch.object(watcher, "parse_app_entries", return_value=[entry]), \
            patch.object(watcher, "TEMP_DIR", Path(temp_dir)), \
            patch.object(watcher, "NetworkManager"), \
            patch.object(watcher, "_release_asset_names", side_effect=NetworkError("API unavailable")), \
            contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            exit_code = watcher.main()

        self.assertEqual(exit_code, 0)
        self.assertEqual(stdout.getvalue(), "{}\n")
        self.assertIn("API unavailable", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
