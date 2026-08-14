from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
import zipfile

from jsonschema import Draft202012Validator
import json

import RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL as gate


ROOT = Path(__file__).resolve().parents[1]


class V2PythonCertifyFullTests(unittest.TestCase):
    def test_wheel_entry_points_require_exact_v2_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            wheel = Path(raw) / "tev_script_portable_reference-1.0.0-py3-none-any.whl"
            with zipfile.ZipFile(wheel, "w") as archive:
                archive.writestr(
                    "tev_script_portable_reference-1.0.0.dist-info/entry_points.txt",
                    "[console_scripts]\n"
                    "tev-script-v2 = tev_script.cli_v2:main\n"
                    "tev-script-v2-describe = tev_script.describe_v2:main\n",
                )
            observed = gate.read_console_scripts(wheel)
            gate.require_v2_entry_points(observed)
            observed.pop("tev-script-v2")
            with self.assertRaisesRegex(gate.V2PythonCertificationFailure, "entry point"):
                gate.require_v2_entry_points(observed)

    def test_receipt_binds_package_1_0_0_to_language_2_0_0_without_stable_claim(self) -> None:
        identity = gate.GitIdentity("agent/v2", "1" * 40, "2" * 40, "3" * 40)
        receipt = gate.build_receipt(
            identity,
            admission_profile="candidate",
            python_version="3.14.6",
            wheel_filename="tev_script_portable_reference-1.0.0-py3-none-any.whl",
            wheel_sha256="4" * 64,
            v1_python_receipt_sha256="5" * 64,
            descriptor_hash="6" * 64,
        )
        schema = json.loads(
            (ROOT / "schemas" / "tev-script-v2-python-certify-full-receipt.schema.json").read_text(
                encoding="utf-8"
            )
        )
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(receipt)
        self.assertEqual(receipt["package_version"], "1.0.0")
        self.assertEqual(receipt["language_version"], "2.0.0")
        self.assertIs(receipt["python_v2_certify_full"], True)
        self.assertIs(receipt["language_stable"], False)
        body = dict(receipt)
        observed = body.pop("receipt_hash")
        self.assertEqual(observed, gate.canonical_hash(body))

    def test_artifact_directory_must_be_external_and_empty(self) -> None:
        with self.assertRaisesRegex(gate.V2PythonCertificationFailure, "outside"):
            gate.require_artifact_root(ROOT / "artifacts")
        with tempfile.TemporaryDirectory() as raw:
            selected = Path(raw) / "artifacts"
            self.assertEqual(gate.require_artifact_root(selected), selected.resolve())
            (selected / "occupied").write_text("x", encoding="utf-8")
            with self.assertRaisesRegex(gate.V2PythonCertificationFailure, "empty"):
                gate.require_artifact_root(selected)


if __name__ == "__main__":
    unittest.main()
