from __future__ import annotations

from dataclasses import asdict
import copy
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import RUN_TEV_SCRIPT_V3_CERTIFY_FULL as cert
from tev_script.canonical import canonical_json
from tev_script.program_ir_v5_semantic import checkpoint_to_object, initial_process_checkpoint, program_to_object
from tev_script.release_metadata_v3 import validate_release_metadata_v3
from tev_script.runtime_v5_semantic import run_semantic_quantum
from tev_script.source_semantic_process_v3 import compile_semantic_process_v3


_JS_SMOKE_SOURCE = '''
process CertParity version "3.0.0";
authority 3333333333333333333333333333333333333333333333333333333333333333;
quantum_steps 4;
fact closed = door.state ["café"];
fact opened = door.state ["ouvert"];
field theory = [closed];
transform realize effects 1111111111111111111111111111111111111111111111111111111111111111 resources 2222222222222222222222222222222222222222222222222222222222222222 profile world remove [closed] add [opened];
label start = apply realize done;
label done = halt;
entry start;
'''


class V3ReleaseMetadataTests(unittest.TestCase):
    def test_release_metadata_profile_is_internally_coherent(self) -> None:
        value = validate_release_metadata_v3()
        self.assertEqual(value["language_version"], "3.0.0")
        self.assertFalse(value["publication_authority"])
        self.assertFalse(value["merge_authority"])
        if value["release_profile"] == "candidate":
            self.assertFalse(value["stable"])
            self.assertEqual(value["release_status"], "IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED")
        else:
            self.assertEqual(value["release_profile"], "stable_request")
            self.assertTrue(value["stable"])
            self.assertEqual(value["release_status"], "STABLE_ADMISSION_REQUESTED")


class V3CertifyFullContractTests(unittest.TestCase):
    def _body(self) -> dict:
        return cert.build_receipt_body(
            repository="Marcbeacve/TEV-Script",
            branch="agent/tev-script-omega-kernel-v1",
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            v2_base_sha=cert.V2_BASE_SHA,
            feature_matrix_sha256="3" * 64,
            descriptor_hash="4" * 64,
            basis_report_hash="5" * 64,
            v3_test_count=77,
            v3_skipped_tests=0,
            full_test_count=2000,
            full_skipped_tests=0,
            schema_validation="PASS",
            v3_authority_validation="PASS",
            v2_byte_identity="PASS",
            v2_authority_validation="PASS",
            v3_wheel_filename="tev_script_portable_reference-3.0.0-py3-none-any.whl",
            v3_wheel_sha256="6" * 64,
            v3_wheel_reproducible=True,
        )

    def test_receipt_is_self_hashed_and_nonpromotional(self) -> None:
        body = self._body()
        self.assertFalse(body["promotion_authority"])
        self.assertFalse(body["language_stable"])
        self.assertTrue(body["certify_full"])
        self.assertEqual(body["package_release_shape"], "V3_3_0_0_WHEEL_REPRODUCIBLE")
        self.assertTrue(body["v3_wheel_reproducible"])
        receipt = cert.seal_receipt(body)
        self.assertTrue(cert.verify_receipt(receipt))

    def test_tamper_and_fake_stability_reject(self) -> None:
        receipt = cert.seal_receipt(self._body())
        tampered = copy.deepcopy(receipt); tampered["language_stable"] = True
        self.assertFalse(cert.verify_receipt(tampered))

    def test_external_receipt_path_is_create_once(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "v3-certify.json"
            self.assertEqual(cert.validate_external_receipt_path(path), path.resolve())
            path.write_text("occupied", encoding="utf-8")
            with self.assertRaises(ValueError):
                cert.validate_external_receipt_path(path)

    def test_focal_certification_requires_python_javascript_runtime_parity(self) -> None:
        node = shutil.which("node")
        self.assertIsNotNone(node, "Node.js is required for V3 independent-runtime certification")
        runtime = cert.ROOT / "runtime_js_v3" / "runtime_v5_semantic.mjs"
        self.assertTrue(runtime.is_file())
        program = compile_semantic_process_v3(_JS_SMOKE_SOURCE)
        checkpoint = initial_process_checkpoint(program)
        expected = run_semantic_quantum(program, checkpoint)
        request = {
            "program": program_to_object(program),
            "checkpoint": checkpoint_to_object(checkpoint, program),
        }
        completed = subprocess.run(
            (str(node), str(runtime)),
            input=canonical_json(request),
            text=True,
            capture_output=True,
            cwd=cert.ROOT,
            timeout=30,
            check=False,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(completed.stdout, canonical_json(asdict(expected)) + "\n")
        self.assertEqual(json.loads(completed.stdout)["field"]["profile"], "world")


if __name__ == "__main__":
    unittest.main()
