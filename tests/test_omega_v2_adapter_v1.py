from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from tev_script.diagnostics import TevScriptError
from tev_script.omega_kernel_v1 import omega_hash, resource_exact, resource_vector
from tev_script.omega_v2_adapter_v1 import (
    omega_epoch_from_v2_replay,
    project_program_ir_v4,
    replay_and_project_program_ir_v4,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "conformance" / "program-ir-v4-cases.json"


class OmegaV2AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._temporary = tempfile.TemporaryDirectory()
        cls._root = Path(cls._temporary.name)
        fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        cls._cases = {row["profile"]: row for row in fixture["valid_profiles"]}
        cls._irs = {
            profile: cls._compile_case(profile, row)
            for profile, row in cls._cases.items()
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temporary.cleanup()

    @classmethod
    def _run_v2_cli(cls, *arguments: str) -> None:
        completed = subprocess.run(
            (sys.executable, "-m", "tev_script.cli_v2", *arguments),
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=60,
        )
        if completed.returncode != 0:
            raise AssertionError(
                "V2 public CLI failed: "
                + repr(arguments)
                + "\nSTDOUT:\n"
                + completed.stdout
                + "\nSTDERR:\n"
                + completed.stderr
            )

    @classmethod
    def _compile_case(cls, profile: str, row: dict) -> dict:
        source = cls._root / f"{profile}.tevs"
        target = cls._root / f"{profile}.ir.json"
        source.write_text(row["source"], encoding="utf-8")

        if profile in {"pure", "recursive"}:
            cls._run_v2_cli("compile", str(source), "-o", str(target))
        elif profile == "effects":
            scenario = cls._root / "effects.scenario.json"
            cls._run_v2_cli("scenario-effects", str(source), "-o", str(scenario))
            cls._run_v2_cli(
                "compile-effects",
                str(source),
                "--scenario",
                str(scenario),
                "-o",
                str(target),
            )
        elif profile == "effects_r2_plan":
            scenario = cls._root / "effects-r2.scenario.json"
            cls._run_v2_cli("scenario-effects-r2", str(source), "-o", str(scenario))
            cls._run_v2_cli(
                "compile-effects-r2",
                str(source),
                "--scenario",
                str(scenario),
                "-o",
                str(target),
            )
        else:
            raise AssertionError(f"unsupported conformance profile {profile!r}")

        ir = json.loads(target.read_text(encoding="utf-8"))
        if ir["schema"] != row["expected_schema"]:
            raise AssertionError(f"V2 public CLI emitted wrong schema for {profile}")
        if ir["program_ir_hash"] != row["expected_program_ir_hash"]:
            raise AssertionError(f"V2 public CLI emitted wrong hash for {profile}")
        return ir

    def test_pure_ir_projection_binds_existing_v2_hashes(self) -> None:
        ir = self._irs["pure"]
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.source_semantic_hash, ir["source"]["semantic_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-pure")

    def test_recursive_ir_projection_uses_recursive_profile(self) -> None:
        ir = self._irs["recursive"]
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-recursive")

    def test_effects_r1_projection_uses_effects_profile(self) -> None:
        ir = self._irs["effects"]
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-effects-r1")

    def test_effects_r2_projection_uses_r2_validator_and_profile(self) -> None:
        ir = self._irs["effects_r2_plan"]
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.source_semantic_hash, ir["source"]["semantic_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-effects-r2")

    def test_tampered_ir_is_rejected_before_projection(self) -> None:
        tampered = copy.deepcopy(self._irs["pure"])
        tampered["program_ir_hash"] = "0" * 64
        with self.assertRaises(TevScriptError):
            project_program_ir_v4(tampered)

    def test_pure_replay_projection_uses_explicit_absence_hashes(self) -> None:
        ir = self._irs["pure"]
        projected = replay_and_project_program_ir_v4(ir)
        self.assertEqual(projected["program_ir_hash"], ir["program_ir_hash"])
        self.assertNotEqual(
            projected["result_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "result"}),
        )
        self.assertEqual(
            projected["state_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "state"}),
        )
        self.assertEqual(
            projected["observation_transcript_hash"],
            omega_hash(
                {"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "observation_transcript"}
            ),
        )
        self.assertEqual(
            projected["effect_receipt_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "effect_receipt"}),
        )

    def test_effects_r1_replay_projection_preserves_real_causal_hashes(self) -> None:
        projected = replay_and_project_program_ir_v4(self._irs["effects"])
        self.assertEqual(len(projected["state_hash"]), 64)
        self.assertEqual(len(projected["observation_transcript_hash"]), 64)
        self.assertEqual(len(projected["effect_receipt_hash"]), 64)
        self.assertNotEqual(
            projected["state_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "state"}),
        )
        self.assertNotEqual(
            projected["effect_receipt_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "effect_receipt"}),
        )

    def test_effects_r2_replay_projection_preserves_planning_evidence(self) -> None:
        ir = self._irs["effects_r2_plan"]
        projected = replay_and_project_program_ir_v4(ir)
        self.assertEqual(projected["program_ir_hash"], ir["program_ir_hash"])
        self.assertEqual(len(projected["state_hash"]), 64)
        self.assertEqual(len(projected["effect_receipt_hash"]), 64)
        self.assertNotEqual(
            projected["effect_receipt_hash"],
            omega_hash({"schema": "TEV_SCRIPT_OMEGA_ABSENT_V1", "kind": "effect_receipt"}),
        )

    def test_pure_v2_replay_can_be_wrapped_as_epoch_and_continuation(self) -> None:
        ir = self._irs["pure"]
        resources = resource_vector(cpu=resource_exact(1))
        epoch, continuation = omega_epoch_from_v2_replay(
            ir,
            epoch_index=0,
            input_state_hash="a" * 64,
            authority_hash="b" * 64,
            previous_continuation_hash=None,
            resources=resources,
        )
        projection = replay_and_project_program_ir_v4(ir)
        self.assertEqual(epoch.computation_hash, project_program_ir_v4(ir).identity_hash)
        self.assertEqual(continuation.result_hash, projection["result_hash"])
        self.assertEqual(continuation.resources_hash, resources.vector_hash)
        self.assertEqual(continuation.epoch_hash, epoch.epoch_hash)


if __name__ == "__main__":
    unittest.main()
