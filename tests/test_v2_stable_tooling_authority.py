from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import tools.validate_v2_authority as semantic_authority
import tools.validate_v2_stable_tooling_authority as tooling
from tev_script import descriptor_v2
from tev_script import release_metadata_v2 as release_metadata

ROOT = Path(__file__).resolve().parents[1]


class V2StableToolingAuthorityTests(unittest.TestCase):
    def test_historical_semantic_authority_remains_unchanged(self) -> None:
        self.assertEqual(len(descriptor_v2.V2_SCHEMA_PATHS), 4)
        self.assertEqual(len(semantic_authority.AUTHORITY_PATHS), 8)
        for relative in tooling.SCHEMA_PATHS:
            self.assertNotIn(relative, semantic_authority.AUTHORITY_PATHS)

    def test_validator_cli_can_import_package_from_tools_path_execution(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                str(ROOT / "tools" / "validate_v2_stable_tooling_authority.py"),
                "--profile",
                release_metadata.RELEASE_PROFILE,
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        self.assertEqual(
            completed.returncode,
            0,
            completed.stdout + "\n" + completed.stderr,
        )
        self.assertIn(
            "TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY=PASS",
            completed.stdout,
        )

    def _fixture(self, root: Path, *, stable: bool) -> None:
        for relative in tooling.STABLE_TOOLING_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            if relative in tooling.SCHEMA_PATHS:
                source = ROOT / relative
                path.write_text(
                    source.read_text(encoding="utf-8"), encoding="utf-8"
                )
            else:
                path.write_text("# tooling fixture\n", encoding="utf-8")
        surface = tooling._expected_surface(stable)
        target = {
            "language_version": "2.0.0",
            "stable_tooling_authority": list(tooling.STABLE_TOOLING_PATHS),
            "gates": dict(tooling.EXPECTED_GATES),
            "stable_release_surface": surface,
        }
        matrix = {
            "stable_tooling_authority": list(tooling.STABLE_TOOLING_PATHS),
        }
        (root / "spec").mkdir(parents=True, exist_ok=True)
        (root / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json").write_text(
            json.dumps(matrix), encoding="utf-8"
        )
        (root / "CANONICAL_INDEX.json").write_text(
            json.dumps({"candidate_language_targets": [target]}),
            encoding="utf-8",
        )

    def test_current_tooling_authority_is_exact(self) -> None:
        release_metadata.validate_release_metadata()
        profile = release_metadata.RELEASE_PROFILE
        stable = release_metadata.STABLE
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._fixture(root, stable=stable)
            tooling.validate_stable_tooling_authority(profile, root=root)

    def test_inventory_or_surface_drift_fails_closed(self) -> None:
        release_metadata.validate_release_metadata()
        profile = release_metadata.RELEASE_PROFILE
        stable = release_metadata.STABLE
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._fixture(root, stable=stable)
            matrix_path = root / "spec" / "TEV_SCRIPT_V2_FEATURE_MATRIX.json"
            matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
            matrix["stable_tooling_authority"].pop()
            matrix_path.write_text(json.dumps(matrix), encoding="utf-8")
            with self.assertRaisesRegex(
                tooling.V2StableToolingAuthorityFailure,
                "INVENTORY",
            ):
                tooling.validate_stable_tooling_authority(profile, root=root)

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            self._fixture(root, stable=stable)
            index_path = root / "CANONICAL_INDEX.json"
            index = json.loads(index_path.read_text(encoding="utf-8"))
            index["candidate_language_targets"][0]["stable_release_surface"][
                "stable_claim"
            ] = not stable
            index_path.write_text(json.dumps(index), encoding="utf-8")
            with self.assertRaisesRegex(
                tooling.V2StableToolingAuthorityFailure,
                "SURFACE",
            ):
                tooling.validate_stable_tooling_authority(profile, root=root)


if __name__ == "__main__":
    unittest.main()
