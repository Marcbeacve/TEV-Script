from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.pipeline_v1 import analyze_v1_paths
from tev_script.project_v1 import load_v1_project, verify_v1_project_inputs

ROOT = Path(__file__).resolve().parents[1]
ECOSYSTEM = ROOT / "examples" / "v1" / "ecosystem"
PROJECT = ECOSYSTEM / "tevscript.project.json"


class V1ProjectManifestTests(unittest.TestCase):
    def test_repository_example_project_loads_and_links(self) -> None:
        project = load_v1_project(PROJECT)
        self.assertEqual(project.default_target, "auto")
        self.assertEqual(
            project.relative_sources,
            ("main.tevs", "model.tevs", "rules.tevs", "storage.tevs"),
        )
        self.assertRegex(project.manifest_hash, r"^[0-9a-f]{64}$")
        self.assertRegex(project.project_input_hash, r"^[0-9a-f]{64}$")
        analysis = analyze_v1_paths(project.source_paths)
        self.assertEqual(analysis.plan.program_id, "Ecosystem")
        self.assertFalse(analysis.ir_v2_boundary.lowerable)
        verify_v1_project_inputs(project, project.input_witness())

    def test_manifest_source_order_does_not_change_project_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_minimal_sources(root)
            first = root / "first.json"
            second = root / "second.json"
            self._write_manifest(first, ["main.tevs", "module.tevs"])
            self._write_manifest(second, ["module.tevs", "main.tevs"])
            a = load_v1_project(first)
            b = load_v1_project(second)
            self.assertEqual(a.canonical_json, b.canonical_json)
            self.assertEqual(a.manifest_hash, b.manifest_hash)
            self.assertEqual(a.project_input_hash, b.project_input_hash)

    def test_source_content_changes_input_hash_but_not_manifest_hash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_minimal_sources(root)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["main.tevs", "module.tevs"])
            before = load_v1_project(manifest)
            (root / "module.tevs").write_text(
                'module m version "1.0.0"; export fn twice(x: Int) -> Int = x * 3;\n',
                encoding="utf-8",
            )
            after = load_v1_project(manifest)
            self.assertEqual(before.manifest_hash, after.manifest_hash)
            self.assertNotEqual(before.project_input_hash, after.project_input_hash)
            with self.assertRaises(TevScriptError) as captured:
                verify_v1_project_inputs(before)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_INPUT_CHANGED")

    def test_manifest_target_changes_manifest_and_input_identity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_minimal_sources(root)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["main.tevs", "module.tevs"], target="auto")
            auto = load_v1_project(manifest)
            self._write_manifest(manifest, ["main.tevs", "module.tevs"], target="irv3")
            irv3 = load_v1_project(manifest)
            self.assertNotEqual(auto.manifest_hash, irv3.manifest_hash)
            self.assertNotEqual(auto.project_input_hash, irv3.project_input_hash)

    def test_rejects_duplicate_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_minimal_sources(root)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["main.tevs", "main.tevs"])
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_SOURCE_DUPLICATE")

    def test_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["../outside.tevs"])
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_SOURCE_TRAVERSAL")

    def test_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["/absolute.tevs"])
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_SOURCE_ABSOLUTE")

    def test_rejects_backslash_separator(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project.json"
            self._write_manifest(manifest, ["folder\\main.tevs"])
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_SOURCE_SEPARATOR")

    def test_rejects_unknown_manifest_field(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "project.json"
            value = self._manifest_value(["main.tevs"])
            value["glob"] = "**/*.tevs"
            manifest.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(TevScriptError) as captured:
                load_v1_project(manifest)
            self.assertEqual(captured.exception.diagnostic.code, "TEVS_V1_PROJECT_FIELDS")

    @staticmethod
    def _manifest_value(sources: list[str], target: str = "auto") -> dict[str, object]:
        return {
            "schema": "TEV_SCRIPT_PROJECT_V1",
            "language_version": "1.0.0",
            "default_target": target,
            "sources": sources,
        }

    @classmethod
    def _write_manifest(cls, path: Path, sources: list[str], target: str = "auto") -> None:
        path.write_text(json.dumps(cls._manifest_value(sources, target)), encoding="utf-8")

    @staticmethod
    def _write_minimal_sources(root: Path) -> None:
        (root / "main.tevs").write_text(
            'script P version "1.0.0"; import m; entity E { on start { return; } }\n',
            encoding="utf-8",
        )
        (root / "module.tevs").write_text(
            'module m version "1.0.0"; export fn twice(x: Int) -> Int = x * 2;\n',
            encoding="utf-8",
        )


if __name__ == "__main__":
    unittest.main()
