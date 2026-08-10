from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    CommitResultV1,
    PreparedReactionV1,
    PreparabilityResultV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from tev_script.semantic_causal_bridge_v0 import (
    capability_law_catalog_field,
    causal_semantic_snapshot,
    commit_result_field,
    prepared_reaction_field,
    reaction_contract_field,
    reaction_footprint_field,
    refinement_receipt_field,
    residual_from_commit_result_v1,
    residual_from_preparability_result_v1,
    residual_from_refinement_receipt_v1,
)
from tev_script.semantic_residual_v0 import parse_residual


def _sha(label: str) -> str:
    return canonical_hash({"label": label})


def _footprint() -> ReactionFootprintV1:
    return ReactionFootprintV1(
        program_semantic_hash=_sha("program"),
        source_semantic_hash=_sha("source"),
        entity_id="E",
        trigger_event="go",
        reachable_events=("go",),
        state_reads=("x",),
        state_writes=("x",),
        observations=(),
        effects=(),
        emitted_events=(),
        capability_occurrences=(),
        reachable_handler_count=1,
        maximum_event_chain=1,
        instruction_ceiling=16,
        cyclic_event_graph=False,
    )


def _contract() -> ReactionContractV1:
    return ReactionContractV1(
        contract_id="contract.demo",
        entity_id="E",
        trigger_event="go",
        allowed_state_reads=("x",),
        allowed_state_writes=("x",),
        maximum_reachable_events=1,
        maximum_instruction_ceiling=16,
        required_atomicity="state_atomic",
    )


def _catalog() -> CapabilityLawCatalogV1:
    return CapabilityLawCatalogV1("deployment.demo", True)


def _refinement(status: str, *, failures=(), pending=()) -> RefinementReceiptV1:
    footprint = _footprint()
    contract = _contract()
    catalog = _catalog()
    return RefinementReceiptV1(
        contract_hash=contract.contract_hash,
        candidate_program_semantic_hash=footprint.program_semantic_hash,
        footprint_hash=footprint.footprint_hash,
        law_catalog_hash=catalog.catalog_hash,
        status=status,
        failures=failures,
        pending_obligations=pending,
    )


def _prepared() -> PreparedReactionV1:
    footprint = _footprint()
    contract = _contract()
    catalog = _catalog()
    refinement = _refinement("PASS")
    before = {"schema": "TEST_CHECKPOINT", "value": 0}
    after = {"schema": "TEST_CHECKPOINT", "value": 1}
    return PreparedReactionV1(
        program_semantic_hash=footprint.program_semantic_hash,
        source_semantic_hash=footprint.source_semantic_hash,
        contract_hash=contract.contract_hash,
        law_catalog_hash=catalog.catalog_hash,
        refinement_receipt_hash=refinement.receipt_hash,
        footprint_hash=footprint.footprint_hash,
        entity_id="E",
        trigger_event="go",
        arguments=(),
        before_checkpoint=before,
        before_checkpoint_hash=canonical_hash(before),
        after_checkpoint=after,
        after_checkpoint_hash=canonical_hash(after),
        observations=(),
        effect_intents=(),
        emitted_events=(),
        atomicity="state_atomic",
        preparation_evidence=("test",),
    )


class SemanticCausalBridgeV0Tests(unittest.TestCase):
    def test_all_primary_causal_artifacts_are_fields(self) -> None:
        contract = _contract()
        catalog = _catalog()
        footprint = _footprint()
        refinement = _refinement("PASS")
        prepared = _prepared()
        commit = CommitResultV1(
            "COMMITTED",
            prepared.prepared_reaction_hash,
            True,
            False,
            0,
            (),
        )
        fields = (
            reaction_contract_field(contract),
            capability_law_catalog_field(catalog),
            reaction_footprint_field(footprint),
            refinement_receipt_field(refinement),
            prepared_reaction_field(prepared),
            commit_result_field(commit),
        )
        self.assertTrue(all(field.facts_for("tev.causal.artifact") for field in fields))
        snapshot = causal_semantic_snapshot(*fields)
        self.assertEqual(len(snapshot.facts_for("tev.causal.artifact")), 6)
        self.assertEqual(snapshot.declarations, (
            ("tev.causal.artifact", 4),
            ("tev.causal.binding", 3),
        ))

    def test_preparability_closed_when_preparable(self) -> None:
        residual = residual_from_preparability_result_v1(
            PreparabilityResultV1(True, "state_atomic", (), ()),
            footprint=_footprint(),
            laws=_catalog(),
        )
        view = parse_residual(residual)
        self.assertTrue(view.closed)
        self.assertEqual(view.domain, "causal")

    def test_preparability_hazard_becomes_structured_residual(self) -> None:
        residual = residual_from_preparability_result_v1(
            PreparabilityResultV1(
                False,
                "interleaved",
                ("effect_observation_staging_hazard",),
                (("storage.write", "sensor.read"),),
            )
        )
        view = parse_residual(residual)
        self.assertFalse(view.closed)
        self.assertEqual(
            {item.kind for item in view.obstructions},
            {"causal.preparability_reason", "causal.staging_hazard"},
        )

    def test_preparability_inconsistent_success_fails_closed(self) -> None:
        with self.assertRaises(ValueError):
            residual_from_preparability_result_v1(
                PreparabilityResultV1(True, "state_atomic", ("unexpected",), ())
            )

    def test_refinement_pass_closes(self) -> None:
        view = parse_residual(residual_from_refinement_receipt_v1(_refinement("PASS")))
        self.assertTrue(view.closed)
        self.assertEqual(view.domain, "refinement")

    def test_refinement_reject_preserves_failure_detail(self) -> None:
        receipt = _refinement(
            "REJECT",
            failures=({"kind": "effects", "extra": ["world.write"]},),
        )
        view = parse_residual(residual_from_refinement_receipt_v1(receipt))
        self.assertFalse(view.closed)
        self.assertEqual(len(view.obstructions), 1)
        self.assertEqual(view.obstructions[0].kind, "refinement.failure")
        self.assertEqual(view.obstructions[0].detail["kind"], "effects")
        self.assertEqual(view.obstructions[0].evidence_hash, receipt.receipt_hash)

    def test_refinement_proof_required_preserves_obligation_identity(self) -> None:
        view = parse_residual(
            residual_from_refinement_receipt_v1(
                _refinement("PROOF_REQUIRED", pending=("proof.contract.demo",))
            )
        )
        self.assertFalse(view.closed)
        self.assertEqual(view.obstructions[0].kind, "proof.required")
        self.assertEqual(view.obstructions[0].subject, "proof.contract.demo")

    def test_commit_success_closes(self) -> None:
        prepared = _prepared()
        result = CommitResultV1(
            "COMMITTED", prepared.prepared_reaction_hash, True, False, 0, ()
        )
        view = parse_residual(residual_from_commit_result_v1(result))
        self.assertTrue(view.closed)
        self.assertEqual(view.domain, "operational")

    def test_commit_abort_partial_and_law_violation_remain_open(self) -> None:
        prepared_hash = _prepared().prepared_reaction_hash
        cases = (
            (
                CommitResultV1("ABORTED", prepared_hash, False, False, 0, (), "prepare failed"),
                "operational.application_aborted",
            ),
            (
                CommitResultV1("EXTERNAL_PARTIAL", prepared_hash, False, True, 1, (), "effect failed"),
                "operational.partial_commit",
            ),
            (
                CommitResultV1("LAW_VIOLATION", prepared_hash, False, True, 1, (), "commit totality violated"),
                "operational.law_violation",
            ),
        )
        for result, kind in cases:
            with self.subTest(status=result.status):
                view = parse_residual(residual_from_commit_result_v1(result))
                self.assertFalse(view.closed)
                self.assertEqual(view.obstructions[0].kind, kind)
                self.assertEqual(view.obstructions[0].dependency_refs, (prepared_hash,))

    def test_commit_flag_inconsistency_fails_closed(self) -> None:
        prepared_hash = _prepared().prepared_reaction_hash
        with self.assertRaises(ValueError):
            residual_from_commit_result_v1(
                CommitResultV1("COMMITTED", prepared_hash, False, False, 0, ())
            )


if __name__ == "__main__":
    unittest.main()
