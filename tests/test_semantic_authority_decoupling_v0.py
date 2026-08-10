from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
import unittest

from tools.v1_optimizer_oracle_contract import (
    OPTIMIZER_ORACLE_SCHEMA_V1,
    OptimizerOracleContractError,
    optimizer_oracle_receipt_line,
    parse_optimizer_oracle_output,
)
from tools.v1_optimizer_oracle_local import build_receipt

ROOT = Path(__file__).resolve().parents[1]


class SemanticAuthorityDecouplingV0Tests(unittest.TestCase):
    def test_local_oracle_is_self_contained_and_negative_controlled(self):
        receipt = build_receipt()
        self.assertEqual(receipt["provider_kind"], "local")
        self.assertTrue(receipt["all_agree"])
        self.assertTrue(receipt["negative_controls_detected"])
        self.assertFalse(receipt["universal_integer_equivalence_proved"])
        self.assertFalse(receipt["promotion_authority"])

    def test_provider_neutral_contract_roundtrip(self):
        receipt = build_receipt()
        stdout = optimizer_oracle_receipt_line(receipt) + "\nTEV_SCRIPT_V1_OPTIMIZER_ORACLE=PASS\n"
        parsed = parse_optimizer_oracle_output(stdout)
        self.assertEqual(parsed["schema"], OPTIMIZER_ORACLE_SCHEMA_V1)
        self.assertEqual(parsed["provider_id"], receipt["provider_id"])

    def test_contract_rejects_elevated_authority(self):
        receipt = build_receipt()
        receipt["promotion_authority"] = True
        with self.assertRaises(OptimizerOracleContractError):
            optimizer_oracle_receipt_line(receipt)

    def test_performance_gate_defaults_to_local_oracle(self):
        spec = importlib.util.spec_from_file_location(
            "performance_polish", ROOT / "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        completed, receipt = module._optimizer_oracle("")
        self.assertEqual(completed.returncode, 0)
        assert receipt is not None
        self.assertEqual(receipt["provider_kind"], "local")

    def test_performance_surface_has_no_external_provider_requirement(self):
        combined = (ROOT / "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.py").read_text(encoding="utf-8")
        combined += (ROOT / "RUN_TEV_SCRIPT_V1_PERFORMANCE_POLISH.ps1").read_text(encoding="utf-8")
        lower = combined.lower()
        self.assertNotIn("tevprover", lower)
        self.assertNotIn("tevprover_root", lower)
        self.assertNotIn("--tevprover-root", lower)
        self.assertIn("--optimizer-oracle", combined)

    def test_authority_validator_allows_nonnormative_research_correspondence(self):
        validator = (ROOT / "tools" / "validate_semantic_authority_decoupling_v0.py").read_text(encoding="utf-8")
        self.assertIn("AUTHORITY_ROOTS", validator)
        self.assertIn("AUTHORITY_FILES", validator)
        self.assertNotIn("git ls-files", validator)

    def test_decoupling_validator(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "validate_semantic_authority_decoupling_v0.py")],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("TEV_SCRIPT_SEMANTIC_AUTHORITY_DECOUPLING_V0=PASS", result.stdout)
        self.assertIn("TEV_SCRIPT_NONNORMATIVE_RESEARCH_CORRESPONDENCE_ALLOWED=PASS", result.stdout)


if __name__ == "__main__":
    unittest.main()
