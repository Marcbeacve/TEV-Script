from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.project_v1 import load_v1_project


class V1ProjectPathSpellingTests(unittest.TestCase):
    def test_repeated_separator_is_rejected_not_normalized(self) -> None:
        self._expect_source_path_failure(
            "folder//main.tevs",
            "TEVS_V1_PROJECT_SOURCE_TRAVERSAL",
        )

    def test_dot_segment_is_rejected_not_normalized(self) -> None:
        self._expect_source_path_failure(
            "folder/./main.tevs",
            "TEVS_V1_PROJECT_SOURCE_TRAVERSAL",
        )

    def test_trailing_separator_is_rejected(self) -> None:
        self._expect_source_path_failure(
            "main.tevs/",
            "TEVS_V1_PROJECT_SOURCE_TRAVERSAL",
        )

    def _expect_source_path_failure(self, source: str, code: str) -> None:
        with tempfile.TemporaryDirectory() as directory:
            manifest = Path(directory) / "project.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema": "TEV_SCRIPT_PROJECT_V1",
                        "language_version": "1.0.0",
                        "default_target": "auto",
                        "sources": [source],
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, code)


if __name__ == "__main__":
    unittest.main()
