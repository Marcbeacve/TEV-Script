from __future__ import annotations

import copy

import pytest

from tev_script.axiomatic_formal_receipt_v0 import (
    AxiomaticFormalReceiptError,
    build_axiomatic_formal_receipt_v0,
    verify_axiomatic_formal_receipt_v0,
)

HEX_A = "a" * 64
HEX_B = "b" * 64
HEX_C = "c" * 64
HEAD = "1" * 40
TREE = "2" * 40


def _artifacts() -> dict[str, str]:
    return {
        "spec/TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0.md": HEX_A,
        "spec/TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0.md": HEX_A,
        "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json": HEX_A,
        "spec/TEV_SCRIPT_AXIOM_COVERAGE_V0.json": HEX_A,
        "formal/lean/TEVScriptAxiomsV0.lean": HEX_A,
        "formal/smt/tev_script_axioms_theorems_v0.smt2": HEX_A,
        "formal/smt/tev_script_axioms_model_v0.smt2": HEX_A,
        "formal/smt/tev_script_axioms_negative_control_v0.smt2": HEX_A,
        "formal/smt/tev_script_operational_axioms_v0.smt2": HEX_A,
        "formal/smt/tev_script_effect_negative_control_v0.smt2": HEX_A,
        "formal/tevprover/TEVScriptFourValueV0.proof.json": HEX_C,
    }


def _repotalk() -> dict[str, str]:
    return {
        "LEAN_ABSTRACT_THEORY": HEX_A,
        "Z3_THEOREMS": HEX_A,
        "Z3_NONCOLLAPSE_MODEL": HEX_A,
        "Z3_SELECTION_NEGATIVE_CONTROL": HEX_A,
        "Z3_OPERATIONAL_THEOREMS": HEX_A,
        "Z3_EFFECT_NEGATIVE_CONTROL": HEX_A,
    }


def _scope() -> dict[str, object]:
    return {
        "policy_id": "TEVPROVER_POLICY_V2",
        "frame": "TEV_NATIVE_EXACT_FINITE",
        "goal_kind": "finite_relation_graph",
        "semantic_domain": "FINITE_RELATIONAL",
        "quantification": "FINITE_WITNESS_CARRIER",
        "strength": "STRUCTURAL_CHECK",
        "external_authority_bool": False,
        "universal_claim_bool": False,
        "claim_id_semantic_authority_bool": False,
        "scope_source": "KERNEL_GOAL_KIND",
        "requested_scope_present_bool": False,
        "boundary_violation": None,
    }


def _receipt():
    return build_axiomatic_formal_receipt_v0(
        branch="realization-semantics-r0",
        head=HEAD,
        tree=TREE,
        artifact_hashes=_artifacts(),
        repotalk_result_hashes=_repotalk(),
        tevprover_proof_file_sha256=HEX_C,
        tevprover_proof_object_sha256=HEX_B,
        tevprover_result_document_sha256=HEX_A,
        tevprover_certified_scope=_scope(),
    )


def test_axiomatic_formal_receipt_roundtrip() -> None:
    receipt = _receipt()
    parsed = verify_axiomatic_formal_receipt_v0(
        receipt.to_object(),
        expected_receipt_hash=receipt.receipt_hash,
        expected_source_head=HEAD,
        expected_source_tree=TREE,
    )
    assert parsed.receipt_hash == receipt.receipt_hash


def test_axiomatic_formal_receipt_rejects_tamper() -> None:
    receipt = _receipt().to_object()
    tampered = copy.deepcopy(receipt)
    tampered["verification"]["repotalk_lean"] = "HOLD"
    with pytest.raises(AxiomaticFormalReceiptError):
        verify_axiomatic_formal_receipt_v0(
            tampered,
            expected_receipt_hash=receipt["receipt_hash"],
            expected_source_head=HEAD,
            expected_source_tree=TREE,
        )


def test_axiomatic_formal_receipt_rejects_authority_escalation() -> None:
    receipt = _receipt().to_object()
    tampered = copy.deepcopy(receipt)
    tampered["authority"]["truth_authority"] = True
    with pytest.raises(AxiomaticFormalReceiptError):
        verify_axiomatic_formal_receipt_v0(
            tampered,
            expected_receipt_hash=receipt["receipt_hash"],
            expected_source_head=HEAD,
            expected_source_tree=TREE,
        )
