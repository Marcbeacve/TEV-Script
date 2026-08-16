from __future__ import annotations

from dataclasses import dataclass
import hmac
from typing import Any

from .canonical import canonical_hash
from .omega_semantic_basis_v1 import field_fact, field_transformation, semantic_field
from .program_ir_v5_semantic import (
    SemanticProcessProgramV1,
    instruction_apply,
    instruction_branch_fact,
    instruction_halt,
    instruction_jump,
    program_to_object,
    semantic_process_program,
    validate_semantic_process_program,
)
from .source_semantic_process_v3 import SemanticProcessSourceV3, parse_semantic_process_v3

RECEIPT_SCHEMA = "TEV_SCRIPT_V3_SOURCE_TO_IR_VALIDATION_RECEIPT_V1"
VERIFIER_ID = "tev.v3.source_to_ir.independent_lowering_v1"

@dataclass(frozen=True, slots=True)
class SourceToIrValidationReceiptV1:
    schema: str
    verifier_id: str
    source_semantic_hash: str
    expected_program_hash: str
    candidate_program_hash: str
    candidate_artifact_hash: str
    status: str
    admission_authority: bool
    promotion_authority: bool
    receipt_hash: str


def _independent_lower(model: SemanticProcessSourceV3) -> SemanticProcessProgramV1:
    facts = {row.name: row.fact for row in model.facts}
    initial = semantic_field(tuple(facts[name] for name in model.field_fact_names), profile=model.field_profile)
    txs = {
        row.name: field_transformation(
            transformation_id=row.name,
            remove_fact_hashes=tuple(facts[name].fact_hash for name in row.remove_names),
            add_facts=tuple(facts[name] for name in row.add_names),
            effect_set_hash=row.effect_set_hash,
            resource_vector_hash=row.resource_vector_hash,
        )
        for row in model.transformations
    }
    labels = tuple(sorted(model.labels, key=lambda row: row.name))
    label_pc = {row.name: index for index, row in enumerate(labels)}
    code = []
    for row in labels:
        if row.kind == "halt":
            code.append(instruction_halt())
        elif row.kind == "jump":
            code.append(instruction_jump(label_pc[row.operands[0]]))
        elif row.kind == "apply":
            tx_name, target = row.operands
            code.append(instruction_apply(txs[tx_name].transformation_hash, next_pc=label_pc[target]))
        elif row.kind == "branch_fact":
            fact_name, present, absent = row.operands
            code.append(instruction_branch_fact(facts[fact_name].fact_hash, present_pc=label_pc[present], absent_pc=label_pc[absent]))
        else:
            raise AssertionError("parser admitted unknown label kind")
    return semantic_process_program(
        program_id=model.program_id,
        source_semantic_hash=model.source_semantic_hash,
        initial_field=initial,
        transformations=tuple(txs.values()),
        instructions=tuple(code),
        entry_pc=label_pc[model.entry_label],
        quantum_step_limit=model.quantum_step_limit,
        authority_hash=model.authority_hash,
    )


def _body(source_hash: str, expected_hash: str, candidate_hash: str, artifact_hash: str, status: str) -> dict[str, Any]:
    return {
        "schema": RECEIPT_SCHEMA,
        "verifier_id": VERIFIER_ID,
        "source_semantic_hash": source_hash,
        "expected_program_hash": expected_hash,
        "candidate_program_hash": candidate_hash,
        "candidate_artifact_hash": artifact_hash,
        "status": status,
        "admission_authority": True,
        "promotion_authority": False,
    }


def validate_source_to_ir_v3(source: str, candidate: SemanticProcessProgramV1) -> SourceToIrValidationReceiptV1:
    model = parse_semantic_process_v3(source)
    expected = _independent_lower(model)
    candidate = validate_semantic_process_program(candidate)
    artifact_hash = canonical_hash(program_to_object(candidate))
    status = "PASS" if candidate.source_semantic_hash == model.source_semantic_hash and candidate.program_hash == expected.program_hash else "REJECT"
    body = _body(model.source_semantic_hash, expected.program_hash, candidate.program_hash, artifact_hash, status)
    return SourceToIrValidationReceiptV1(
        RECEIPT_SCHEMA,
        VERIFIER_ID,
        model.source_semantic_hash,
        expected.program_hash,
        candidate.program_hash,
        artifact_hash,
        status,
        True,
        False,
        canonical_hash(body),
    )


def verify_source_to_ir_validation(source: str, candidate: SemanticProcessProgramV1, receipt: SourceToIrValidationReceiptV1) -> bool:
    try:
        expected = validate_source_to_ir_v3(source, candidate)
        return bool(isinstance(receipt, SourceToIrValidationReceiptV1) and hmac.compare_digest(receipt.receipt_hash, expected.receipt_hash) and receipt == expected)
    except Exception:
        return False


def source_to_ir_validation_field(receipt: SourceToIrValidationReceiptV1):
    if not isinstance(receipt, SourceToIrValidationReceiptV1):
        raise TypeError("SourceToIrValidationReceiptV1 required")
    return semantic_field((field_fact(
        "tev.proof.source_to_ir",
        (
            receipt.receipt_hash,
            receipt.verifier_id,
            receipt.source_semantic_hash,
            receipt.expected_program_hash,
            receipt.candidate_program_hash,
            receipt.candidate_artifact_hash,
            receipt.status,
            receipt.admission_authority,
            receipt.promotion_authority,
        ),
    ),), profile="proof_validation")

__all__ = ["SourceToIrValidationReceiptV1", "source_to_ir_validation_field", "validate_source_to_ir_v3", "verify_source_to_ir_validation"]
