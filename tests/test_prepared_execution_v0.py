from __future__ import annotations

import unittest

from tev_script.canonical import canonical_hash
from tev_script.causal_model_v1 import (
    CapabilityLawCatalogV1,
    PreparedReactionV1,
    ReactionContractV1,
    ReactionFootprintV1,
    RefinementReceiptV1,
)
from tev_script.causal_refinement_v1 import verify_prepared_refinement
from tev_script.semantic_activation_v0 import (
    ActivationIssueV0,
    ExecutionActivationCandidateV0,
    ExecutionActivationReceiptV0,
)
from tev_script.semantic_execution_authority_v0 import (
    ExecutionAuthorityIssueV0,
    ExecutionAuthorityReceiptV0,
)
from tev_script.semantic_prepared_execution_v0 import (
    PreparedExecutionClaimV0,
    causal_invocation_workload_hash,
    evaluate_prepared_execution,
    residual_from_prepared_execution,
)
from tev_script.semantic_residual_v0 import parse_residual


def h(label: str) -> str:
    return canonical_hash({"test": label})


class PreparedExecutionV0Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.program = h("program")
        self.contract = ReactionContractV1(
            "contract.main",
            "entity.main",
            "start",
            maximum_reachable_events=1,
            maximum_instruction_ceiling=1,
        )
        self.catalog = CapabilityLawCatalogV1("deployment.main", True)
        self.footprint = ReactionFootprintV1(
            self.program,
            h("source"),
            "entity.main",
            "start",
            ("start",),
            (),
            (),
            (),
            (),
            (),
            (),
            1,
            1,
            1,
            False,
        )
        self.before = {
            "schema": "TEST_CHECKPOINT_V0",
            "entities": [],
            "marker": "before",
        }
        self.after = {
            "schema": "TEST_CHECKPOINT_V0",
            "entities": [],
            "marker": "after",
        }
        self.prepared_refinement = verify_prepared_refinement(
            self.contract,
            self.footprint,
            self.catalog,
            self.before,
            self.after,
            "state_atomic",
        )
        self.assertEqual(self.prepared_refinement.status, "PASS")
        self.prepared = self._prepared(self.prepared_refinement)
        self.workload = causal_invocation_workload_hash(self.prepared)
        self.activation_candidate = self._activation_candidate(self.workload)
        self.activation = self._activation_receipt(self.activation_candidate)
        self.authority = self._authority()

    def _prepared(self, refinement: RefinementReceiptV1, *, argument_value: int = 7) -> PreparedReactionV1:
        arguments = (
            {
                "type": "Int",
                "value": {"type": "int", "value": argument_value},
            },
        )
        return PreparedReactionV1(
            self.program,
            h("source"),
            self.contract.contract_hash,
            self.catalog.catalog_hash,
            refinement.receipt_hash,
            self.footprint.footprint_hash,
            "entity.main",
            "start",
            arguments,
            self.before,
            canonical_hash(self.before),
            self.after,
            canonical_hash(self.after),
            (),
            (),
            (),
            "state_atomic",
            ("test-prepared",),
        )

    def _activation_candidate(self, workload_hash: str) -> ExecutionActivationCandidateV0:
        return ExecutionActivationCandidateV0(
            h("realization-receipt"),
            h("placement-evaluation"),
            h("runtime-evaluation"),
            h("runtime-claim"),
            h("execution-context"),
            workload_hash,
            h("environment"),
        )

    def _activation_receipt(
        self,
        candidate: ExecutionActivationCandidateV0,
        *,
        issues=(),
    ) -> ExecutionActivationReceiptV0:
        return ExecutionActivationReceiptV0(
            candidate.activation_candidate_hash,
            candidate.record_hash,
            candidate.realization_receipt_hash,
            h("realization"),
            candidate.placement_evaluation_hash,
            h("machine-instance"),
            h("placement-context"),
            candidate.runtime_state_evaluation_hash,
            candidate.runtime_state_claim_hash,
            candidate.execution_context_hash,
            tuple(issues),
        )

    def _authority(self, *, program=None, issues=()) -> ExecutionAuthorityReceiptV0:
        return ExecutionAuthorityReceiptV0(
            h("authority-claim"),
            h("authority-record"),
            self.activation.realization_receipt_hash if hasattr(self, "activation") else h("realization-receipt"),
            h("realization"),
            h("transformation"),
            h("regime-binding"),
            h("scope"),
            program or self.program,
            self.contract.contract_hash,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            h("structural-refinement"),
            h("binding-evidence-evaluation"),
            h("authority-policy"),
            tuple(issues),
        )

    def _evaluate(
        self,
        *,
        candidate=None,
        activation=None,
        authority=None,
        prepared=None,
        refinement=None,
    ):
        candidate = candidate or self.activation_candidate
        activation = activation or self.activation
        authority = authority or self.authority
        prepared = prepared or self.prepared
        refinement = refinement or self.prepared_refinement
        claim = PreparedExecutionClaimV0(
            activation.receipt_hash,
            authority.receipt_hash,
            prepared.prepared_reaction_hash,
            refinement.receipt_hash,
        )
        return evaluate_prepared_execution(
            claim,
            activation_candidate=candidate,
            activation_receipt=activation,
            execution_authority_receipt=authority,
            prepared_reaction=prepared,
            prepared_refinement_receipt=refinement,
            reaction_contract=self.contract,
            reaction_footprint=self.footprint,
            law_catalog=self.catalog,
        )

    def test_exact_prepared_invocation_closes(self):
        receipt = self._evaluate()
        self.assertEqual(receipt.status, "PASS")
        self.assertEqual(receipt.invocation_workload_hash, self.workload)
        self.assertEqual(receipt.prepared_reaction_hash, self.prepared.prepared_reaction_hash)
        self.assertEqual(receipt.before_checkpoint_hash, canonical_hash(self.before))
        self.assertEqual(receipt.after_checkpoint_hash, canonical_hash(self.after))
        self.assertEqual(parse_residual(residual_from_prepared_execution(receipt)).status, "CLOSED")

    def test_activation_for_other_arguments_cannot_reuse_prepared_reaction(self):
        wrong_candidate = self._activation_candidate(h("other-workload"))
        wrong_activation = self._activation_receipt(wrong_candidate)
        receipt = self._evaluate(candidate=wrong_candidate, activation=wrong_activation)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("prepared_execution.workload_mismatch", {item.kind for item in receipt.issues})

    def test_forged_pass_refinement_is_recomputed_and_rejected(self):
        forged = RefinementReceiptV1(
            self.contract.contract_hash,
            self.program,
            self.footprint.footprint_hash,
            self.catalog.catalog_hash,
            "PASS",
            failures=({"kind": "forged_failure_hidden_by_pass"},),
        )
        forged_prepared = self._prepared(forged)
        forged_workload = causal_invocation_workload_hash(forged_prepared)
        candidate = self._activation_candidate(forged_workload)
        activation = self._activation_receipt(candidate)
        receipt = self._evaluate(
            candidate=candidate,
            activation=activation,
            prepared=forged_prepared,
            refinement=forged,
        )
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("prepared_execution.refinement_revalidation_mismatch", {item.kind for item in receipt.issues})

    def test_prepared_program_must_match_execution_authority_program(self):
        foreign_authority = self._authority(program=h("other-program"))
        receipt = self._evaluate(authority=foreign_authority)
        self.assertEqual(receipt.status, "REJECT")
        self.assertIn("prepared_execution.program_mismatch", {item.kind for item in receipt.issues})

    def test_open_activation_or_authority_propagates_without_reinterpretation(self):
        open_activation = self._activation_receipt(
            self.activation_candidate,
            issues=(
                ActivationIssueV0(
                    "activation.runtime_state_not_admitted",
                    "PROOF_REQUIRED",
                    h("runtime"),
                    {},
                ),
            ),
        )
        open_authority = self._authority(
            issues=(
                ExecutionAuthorityIssueV0(
                    "authority.refinement_not_admitted",
                    "PROOF_REQUIRED",
                    h("refinement"),
                    {},
                ),
            )
        )
        activation_result = self._evaluate(activation=open_activation)
        authority_result = self._evaluate(authority=open_authority)
        self.assertEqual(activation_result.status, "PROOF_REQUIRED")
        self.assertEqual(authority_result.status, "PROOF_REQUIRED")
        self.assertIn("prepared_execution.activation_not_admitted", {item.kind for item in activation_result.issues})
        self.assertIn("prepared_execution.execution_authority_not_admitted", {item.kind for item in authority_result.issues})


if __name__ == "__main__":
    unittest.main()
