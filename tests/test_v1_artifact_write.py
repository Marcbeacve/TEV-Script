from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tev_script.artifact_write_v1 import (
    write_compilation_artifacts_v1,
    write_text_artifact_v1,
)
from tev_script.diagnostics import TevScriptError


class V1ArtifactWriterTests(unittest.TestCase):
    def test_single_artifact_replaces_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "linked.json"
            path.write_text("old\n", encoding="utf-8")
            result = write_text_artifact_v1(path, "new")
            self.assertEqual(result, path.resolve())
            self.assertEqual(path.read_bytes(), b"new\n")
            self.assertEqual(self._temporary_entries(path.parent), [])

    def test_ir_and_receipt_commit_together_on_normal_success(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ir = root / "program.json"
            receipt = root / "receipt.json"
            result = write_compilation_artifacts_v1(
                ir,
                '{"ir":1}',
                receipt_path=receipt,
                receipt_content='{"receipt":1}',
            )
            self.assertEqual(result.ir_path, ir.resolve())
            self.assertEqual(result.receipt_path, receipt.resolve())
            self.assertEqual(ir.read_bytes(), b'{"ir":1}\n')
            self.assertEqual(receipt.read_bytes(), b'{"receipt":1}\n')
            self.assertEqual(self._temporary_entries(root), [])

    def test_receipt_path_is_rejected_when_same_as_ir_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "same.json"
            with self.assertRaises(TevScriptError) as captured:
                write_compilation_artifacts_v1(
                    path,
                    "ir",
                    receipt_path=path,
                    receipt_content="receipt",
                )
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_ARTIFACT_PATH_COLLISION")
            self.assertFalse(path.exists())

    def test_receipt_commit_failure_restores_previous_ir_and_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ir = root / "program.json"
            receipt = root / "receipt.json"
            ir.write_text("old-ir\n", encoding="utf-8")
            receipt.write_text("old-receipt\n", encoding="utf-8")

            real_replace = os.replace
            commit_replace_count = 0

            def failing_replace(source, destination):
                nonlocal commit_replace_count
                destination_path = Path(destination)
                # Count only operations targeting an authoritative artifact path.
                if destination_path in {ir, receipt}:
                    commit_replace_count += 1
                    # receipt backup move targets a backup path, so authoritative
                    # target #1 is new IR and #2 is new receipt.
                    if commit_replace_count == 2:
                        raise OSError("forced receipt install failure")
                return real_replace(source, destination)

            with patch("tev_script.artifact_write_v1.os.replace", side_effect=failing_replace):
                with self.assertRaises(TevScriptError) as captured:
                    write_compilation_artifacts_v1(
                        ir,
                        "new-ir",
                        receipt_path=receipt,
                        receipt_content="new-receipt",
                    )

            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_ARTIFACT_COMMIT")
            self.assertEqual(ir.read_text(encoding="utf-8"), "old-ir\n")
            self.assertEqual(receipt.read_text(encoding="utf-8"), "old-receipt\n")
            self.assertEqual(self._temporary_entries(root), [])

    def test_failure_without_previous_files_leaves_no_authoritative_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            ir = root / "program.json"
            receipt = root / "receipt.json"
            real_replace = os.replace
            authoritative_commits = 0

            def failing_replace(source, destination):
                nonlocal authoritative_commits
                destination_path = Path(destination)
                if destination_path in {ir, receipt}:
                    authoritative_commits += 1
                    if authoritative_commits == 2:
                        raise OSError("forced receipt install failure")
                return real_replace(source, destination)

            with patch("tev_script.artifact_write_v1.os.replace", side_effect=failing_replace):
                with self.assertRaises(TevScriptError):
                    write_compilation_artifacts_v1(
                        ir,
                        "new-ir",
                        receipt_path=receipt,
                        receipt_content="new-receipt",
                    )

            self.assertFalse(ir.exists())
            self.assertFalse(receipt.exists())
            self.assertEqual(self._temporary_entries(root), [])

    @staticmethod
    def _temporary_entries(root: Path) -> list[str]:
        return sorted(
            item.name
            for item in root.iterdir()
            if ".tev-stage-" in item.name or ".tev-backup-" in item.name
        )


if __name__ == "__main__":
    unittest.main()
