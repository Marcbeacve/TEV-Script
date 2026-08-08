from __future__ import annotations

import ast
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_STABLE_PROMOTION_GATES = {
    "STABLE_ADMISSION_TOOLING_TECHNICALLY_CERTIFIED_PASS",
    "STABLE_PARENT_CERTIFICATE_BINDING_PASS",
    "STABLE_RELEASE_DIFF_CONFINEMENT_PASS",
    "STABLE_GLOBAL_PROFILE_RECERTIFICATION_PASS",
    "STABLE_PYTHON_PROFILE_RECERTIFICATION_PASS",
    "STABLE_ARTIFACT_BYTE_IDENTITY_PASS",
    "EXACT_STABLE_ADMISSION_PASS",
}
STAGE_D_PYTHON_AUTHORITIES = (
    "RUN_TEV_SCRIPT_V1_PRECERTIFY.py",
    "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
    "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
    "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
    "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py",
    "tools/validate_v1_governance.py",
    "tools/validate_v1_stable_governance.py",
    "tev_script/descriptor_v1.py",
    "tev_script/release_metadata_v1.py",
)


class V1StableAdmissionAuthorityTests(unittest.TestCase):
    def test_stage_d_authority_python_is_syntactically_closed(self) -> None:
        for relative in STAGE_D_PYTHON_AUTHORITIES:
            path = ROOT / relative
            source = path.read_text(encoding="utf-8")
            with self.subTest(path=relative):
                ast.parse(source, filename=relative, mode="exec")

    def test_only_stable_admission_may_emit_language_stable_yes(self) -> None:
        stable = (ROOT / "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py").read_text(encoding="utf-8")
        global_cert = (ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py").read_text(encoding="utf-8")
        python_cert = (ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py").read_text(encoding="utf-8")
        precertify = (ROOT / "RUN_TEV_SCRIPT_V1_PRECERTIFY.py").read_text(encoding="utf-8")

        self.assertIn('print("LANGUAGE_STABLE=YES")', stable)
        self.assertNotIn('print("LANGUAGE_STABLE=YES")', global_cert)
        self.assertNotIn('print("LANGUAGE_STABLE=YES")', python_cert)
        self.assertNotIn('print("LANGUAGE_STABLE=YES")', precertify)

    def test_stable_admission_requires_exact_parent_certificate(self) -> None:
        stable = (ROOT / "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py").read_text(encoding="utf-8")
        for token in (
            'parser.add_argument("--technical-parent-certificate", required=True)',
            "STABLE_PARENT_CERTIFICATE_HASH",
            'certificate.get("admission_profile"), "candidate"',
            'certificate.get("commit"), parent',
            'certificate.get("certify_full"), True',
            'certificate.get("language_stable"), False',
        ):
            self.assertIn(token, stable)

    def test_release_diff_whitelist_excludes_runtime_compiler_and_gates(self) -> None:
        stable = (ROOT / "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py").read_text(encoding="utf-8")
        allowed_block = stable.split("ALLOWED_RELEASE_PATHS = {", 1)[1].split("}\n", 1)[0]
        for forbidden in (
            "tev_script/runtime_v3.py",
            "tev_script/parser_v1.py",
            "tev_script/linker_v1.py",
            "javascript/src/runtime-v3.mjs",
            "runtimes/csharp",
            "RUN_TEV_SCRIPT_V1_PRECERTIFY.py",
            "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
            "RUN_TEV_SCRIPT_V1_PYTHON_PRODUCTION.py",
            "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py",
            "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py",
        ):
            self.assertNotIn(forbidden, allowed_block)
        for required in (
            "CANONICAL_INDEX.json",
            "CHANGELOG.md",
            "PROJECT_STATE.md",
            "README.md",
            "pyproject.toml",
            "javascript/package.json",
            "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
            "tev_script/release_metadata_v1.py",
        ):
            self.assertIn(required, allowed_block)

    def test_stable_recertifies_global_and_python_profiles(self) -> None:
        stable = (ROOT / "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py").read_text(encoding="utf-8")
        self.assertIn('str(ROOT / "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py")', stable)
        self.assertIn('str(ROOT / "RUN_TEV_SCRIPT_V1_PYTHON_CERTIFY_FULL.py")', stable)
        self.assertGreaterEqual(stable.count('"--profile"'), 2)
        self.assertGreaterEqual(stable.count('"stable"'), 3)
        self.assertIn("STABLE_JAVASCRIPT_TEST=PASS", stable)
        self.assertIn("STABLE_JAVASCRIPT_PACK=PASS", stable)

    def test_javascript_artifact_identity_is_not_filename_only(self) -> None:
        stable = (ROOT / "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py").read_text(encoding="utf-8")
        for token in (
            "STABLE_JAVASCRIPT_PACK_NAME",
            "STABLE_JAVASCRIPT_PACK_VERSION",
            "STABLE_JAVASCRIPT_PACK_FILENAME",
            "STABLE_JAVASCRIPT_PACK_INTEGRITY",
            "sha256_file(package_path)",
            '"javascript_package_sha256": package_hash',
            '"javascript_npm_integrity": declared_integrity',
        ):
            self.assertIn(token, stable)

    def test_feature_matrix_keeps_full_stable_promotion_chain(self) -> None:
        matrix = json.loads(
            (ROOT / "spec" / "TEV_SCRIPT_V1_FEATURE_MATRIX.json").read_text(
                encoding="utf-8"
            )
        )
        promotion = {str(item) for item in matrix["promotion_gates"]}
        self.assertIn("V1_NEGATIVE_BOUNDARY_CAMPAIGN_PASS", promotion)
        self.assertTrue(REQUIRED_STABLE_PROMOTION_GATES.issubset(promotion))

    def test_stable_governance_requires_stable_surface_claim(self) -> None:
        governance = (
            ROOT / "tools" / "validate_v1_stable_governance.py"
        ).read_text(encoding="utf-8")
        self.assertIn('"stable_claim": True', governance)
        self.assertIn("V1_STABLE_GOVERNANCE_STABLE_SURFACE", governance)
        self.assertIn("V1_STABLE_GOVERNANCE_PROMOTION_GATES", governance)


if __name__ == "__main__":
    unittest.main()
