from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from jsonschema import Draft202012Validator

import RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL as gate


ROOT = Path(__file__).resolve().parents[1]


def make_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "tev_script_portable_reference-1.0.0.dist-info/entry_points.txt",
            "[console_scripts]\n"
            "tev-script-v2 = tev_script.cli_v2:main\n"
            "tev-script-v2-describe = tev_script.describe_v2:main\n",
        )


class V2PythonCertifyFullTests(unittest.TestCase):
    def test_wheel_entry_points_require_exact_v2_scripts(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            wheel = Path(raw) / gate.WHEEL_FILENAME
            make_wheel(wheel)
            _, snapshot, _ = gate.load_single_wheel_snapshot(Path(raw))
            observed = gate.read_console_scripts_snapshot(snapshot)
            gate.require_v2_entry_points(observed)
            observed.pop("tev-script-v2")
            with self.assertRaisesRegex(
                gate.V2PythonCertificationFailure,
                "entry point",
            ):
                gate.require_v2_entry_points(observed)

    def test_wheel_snapshot_requires_exactly_one_expected_regular_wheel(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            wheel = root / gate.WHEEL_FILENAME
            make_wheel(wheel)
            selected, snapshot, digest = gate.load_single_wheel_snapshot(root)
            self.assertEqual(selected, wheel)
            self.assertEqual(digest, gate.hash_wheel_snapshot(snapshot))
            self.assertGreater(len(snapshot), 0)

            make_wheel(root / "unexpected-1.0.0-py3-none-any.whl")
            with self.assertRaisesRegex(
                gate.V2PythonCertificationFailure,
                "exactly one wheel",
            ):
                gate.load_single_wheel_snapshot(root)

    def test_exported_wheel_must_remain_byte_identical_to_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            wheel = root / gate.WHEEL_FILENAME
            make_wheel(wheel)
            _, snapshot, digest = gate.load_single_wheel_snapshot(root)
            gate.require_exported_wheel_unchanged(wheel, digest)
            wheel.write_bytes(snapshot + b"mutation")
            with self.assertRaisesRegex(
                gate.V2PythonCertificationFailure,
                "changed during certification",
            ):
                gate.require_exported_wheel_unchanged(wheel, digest)

    def test_v1_python_receipt_binds_exact_source_identity(self) -> None:
        identity = gate.GitIdentity(
            "agent/v2",
            "1" * 40,
            "2" * 40,
            "3" * 40,
        )
        receipt = {
            "admission_profile": "stable",
            "branch": identity.branch,
            "commit": identity.commit_sha,
            "tree": identity.tree_sha,
            "package_name": gate.PACKAGE_NAME,
            "package_version": gate.PACKAGE_VERSION,
            "wheel_filename": gate.WHEEL_FILENAME,
            "wheel_sha256": "4" * 64,
            "python_certify_full": True,
            "language_stable": False,
            "stable_release_authorized": False,
        }
        gate.require_v1_python_receipt_identity(receipt, identity)
        for key, value in (
            ("branch", "agent/other"),
            ("commit", "9" * 40),
            ("tree", "8" * 40),
            ("python_certify_full", False),
            ("language_stable", True),
            ("stable_release_authorized", True),
        ):
            with self.subTest(key=key, value=value):
                substituted = dict(receipt)
                substituted[key] = value
                with self.assertRaisesRegex(
                    gate.V2PythonCertificationFailure,
                    "identity",
                ):
                    gate.require_v1_python_receipt_identity(
                        substituted,
                        identity,
                    )

    def test_installed_descriptor_hash_must_equal_checkout_descriptor_hash(self) -> None:
        gate.require_descriptor_identity("a" * 64, "a" * 64)
        with self.assertRaisesRegex(
            gate.V2PythonCertificationFailure,
            "descriptor identity",
        ):
            gate.require_descriptor_identity("a" * 64, "b" * 64)
        with self.assertRaisesRegex(
            gate.V2PythonCertificationFailure,
            "descriptor identity",
        ):
            gate.require_descriptor_identity("A" * 64, "A" * 64)

    def test_receipt_binds_package_1_0_0_to_language_2_0_0_without_stable_claim(self) -> None:
        identity = gate.GitIdentity("agent/v2", "1" * 40, "2" * 40, "3" * 40)
        receipt = gate.build_receipt(
            identity,
            admission_profile="candidate",
            python_version="3.14.6",
            wheel_filename=gate.WHEEL_FILENAME,
            wheel_sha256="4" * 64,
            v1_python_receipt_sha256="5" * 64,
            descriptor_hash="6" * 64,
        )
        schema = json.loads(
            (
                ROOT
                / "schemas"
                / "tev-script-v2-python-certify-full-receipt.schema.json"
            ).read_text(encoding="utf-8")
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

    def test_receipt_writer_is_create_once(self) -> None:
        identity = gate.GitIdentity("agent/v2", "1" * 40, "2" * 40, "3" * 40)
        receipt = gate.build_receipt(
            identity,
            admission_profile="candidate",
            python_version="3.14.6",
            wheel_filename=gate.WHEEL_FILENAME,
            wheel_sha256="4" * 64,
            v1_python_receipt_sha256="5" * 64,
            descriptor_hash="6" * 64,
        )
        with tempfile.TemporaryDirectory() as raw:
            target = Path(raw) / "v2-python.json"
            gate._write_receipt(target, receipt)
            original = target.read_bytes()
            self.assertEqual(
                original,
                (gate.canonical_json(receipt) + "\n").encode("utf-8"),
            )
            with self.assertRaisesRegex(
                gate.V2PythonCertificationFailure,
                "already exists",
            ):
                gate._write_receipt(target, receipt)
            self.assertEqual(target.read_bytes(), original)

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
