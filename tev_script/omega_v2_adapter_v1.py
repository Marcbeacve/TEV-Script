from __future__ import annotations

from typing import Any, Mapping

from .diagnostics import TevScriptError
from .omega_kernel_v1 import (
    ContinuationReceiptV1,
    EpochIdentityV1,
    KernelComputationIdentityV1,
    ResourceVectorV1,
    continuation_receipt,
    epoch_identity,
    kernel_computation_identity,
    omega_hash,
    omega_wire,
)
from .program_ir_v4 import (
    PROGRAM_IR_V4_EFFECTS_SCHEMA,
    PROGRAM_IR_V4_PURE_SCHEMA,
    PROGRAM_IR_V4_RECURSIVE_SCHEMA,
    ProgramIRV4EffectsRunReceipt,
    ProgramIRV4PureRunReceipt,
    ProgramIRV4RecursiveRunReceipt,
    run_program_ir_v4_effects,
    run_program_ir_v4_pure,
    run_program_ir_v4_recursive,
    validate_program_ir_v4,
)
from .program_ir_v4_effect_commands import (
    PROGRAM_IR_V4_EFFECTS_R2_SCHEMA,
    ProgramIRV4EffectsR2PlanReceipt,
    ProgramIRV4EffectsR2PlanResult,
    plan_program_ir_v4_effects_r2,
    validate_program_ir_v4_effects_r2,
)


RUN_PROJECTION_SCHEMA = "TEV_SCRIPT_OMEGA_V2_RUN_PROJECTION_V1"
ABSENT_SCHEMA = "TEV_SCRIPT_OMEGA_ABSENT_V1"
R2_OBSERVATION_PROJECTION_SCHEMA = "TEV_SCRIPT_OMEGA_V2_R2_OBSERVATION_TRANSCRIPT_V1"

_PROFILE_BY_SCHEMA = {
    PROGRAM_IR_V4_PURE_SCHEMA: "program-ir-v4-pure",
    PROGRAM_IR_V4_RECURSIVE_SCHEMA: "program-ir-v4-recursive",
    PROGRAM_IR_V4_EFFECTS_SCHEMA: "program-ir-v4-effects-r1",
    PROGRAM_IR_V4_EFFECTS_R2_SCHEMA: "program-ir-v4-effects-r2",
}


def project_program_ir_v4(raw: Mapping[str, Any]) -> KernelComputationIdentityV1:
    """Project one already-valid V2 Program IR artifact into an Ω computation identity.

    V2 remains semantic authority. This adapter never reconstructs or relaxes V2
    validation; it delegates to the existing V2 validator for the exact profile
    before reading any identity field.
    """

    if not isinstance(raw, Mapping):
        _fail("TEVS_OMEGA_V2_IR", "Program IR projection requires a mapping")
    schema = raw.get("schema")
    profile = _PROFILE_BY_SCHEMA.get(schema)
    if profile is None:
        _fail("TEVS_OMEGA_V2_PROFILE", f"unsupported V2 Program IR schema {schema!r}")

    if schema == PROGRAM_IR_V4_EFFECTS_R2_SCHEMA:
        validation = validate_program_ir_v4_effects_r2(raw)
    else:
        validation = validate_program_ir_v4(raw)

    source = raw.get("source")
    if not isinstance(source, Mapping) or source.get("language_version") != "2.0.0":
        _fail("TEVS_OMEGA_V2_SOURCE", "validated V2 Program IR must declare language version 2.0.0")

    return kernel_computation_identity(
        language_id="TEV-Script",
        language_version="2.0.0",
        semantic_profile=profile,
        program_hash=validation.program_ir_hash,
        source_semantic_hash=validation.source_semantic_hash,
    )


def project_run_receipt_v4(raw_ir: Mapping[str, Any], receipt: Any) -> dict[str, object]:
    """Project a deterministic V2 run/plan receipt into a closed Ω causal summary.

    Every accepted receipt is reproduced by the authoritative V2 runtime/planner
    and must compare exactly before projection. Profiles without a semantic
    component use a canonical explicit-absence hash rather than zero/empty data.
    """

    identity = project_program_ir_v4(raw_ir)
    schema = raw_ir.get("schema") if isinstance(raw_ir, Mapping) else None

    result_hash = _absent_hash("result")
    state_hash = _absent_hash("state")
    observation_hash = _absent_hash("observation_transcript")
    effect_hash = _absent_hash("effect_receipt")

    if schema == PROGRAM_IR_V4_PURE_SCHEMA:
        expected = run_program_ir_v4_pure(raw_ir)
        _require_exact_receipt(receipt, expected, ProgramIRV4PureRunReceipt, "pure")
        result_hash = expected.result_hash

    elif schema == PROGRAM_IR_V4_RECURSIVE_SCHEMA:
        expected = run_program_ir_v4_recursive(raw_ir)
        _require_exact_receipt(receipt, expected, ProgramIRV4RecursiveRunReceipt, "recursive")
        result_hash = expected.result_hash

    elif schema == PROGRAM_IR_V4_EFFECTS_SCHEMA:
        expected = run_program_ir_v4_effects(raw_ir)
        _require_exact_receipt(receipt, expected, ProgramIRV4EffectsRunReceipt, "effects-r1")
        state_hash = expected.final_state_hash
        observation_hash = expected.capability_transcript_hash
        effect_hash = expected.transition_receipt_hash

    elif schema == PROGRAM_IR_V4_EFFECTS_R2_SCHEMA:
        expected = plan_program_ir_v4_effects_r2(raw_ir)
        candidate_receipt, candidate_artifact = _normalize_r2_receipt(receipt)
        if candidate_receipt != expected.receipt:
            _fail("TEVS_OMEGA_V2_RECEIPT", "Effects R2 plan receipt does not match deterministic V2 replay")
        if candidate_artifact is not None and candidate_artifact != expected.plan_artifact:
            _fail("TEVS_OMEGA_V2_RECEIPT", "Effects R2 plan artifact does not match deterministic V2 replay")
        state_hash = expected.receipt.proposed_final_state_hash
        effect_hash = expected.receipt.planning_receipt_hash
        transcript = expected.plan_artifact.get("capability_transcript")
        if transcript is not None:
            observation_hash = omega_hash(
                {
                    "schema": R2_OBSERVATION_PROJECTION_SCHEMA,
                    "capability_transcript": transcript,
                }
            )

    else:
        _fail("TEVS_OMEGA_V2_PROFILE", f"unsupported V2 Program IR schema {schema!r}")

    payload: dict[str, object] = {
        "schema": RUN_PROJECTION_SCHEMA,
        "computation_identity_hash": identity.identity_hash,
        "program_ir_hash": identity.program_hash,
        "result_hash": result_hash,
        "state_hash": state_hash,
        "observation_transcript_hash": observation_hash,
        "effect_receipt_hash": effect_hash,
    }
    return {**payload, "projection_hash": omega_hash(payload)}


def omega_epoch_from_v2(
    raw_ir: Mapping[str, Any],
    receipt: Any,
    *,
    epoch_index: int,
    input_state_hash: str,
    authority_hash: str,
    previous_continuation_hash: str | None,
    resources: ResourceVectorV1,
) -> tuple[EpochIdentityV1, ContinuationReceiptV1]:
    """Wrap one validated deterministic V2 execution/planning step as an Ω epoch."""

    identity = project_program_ir_v4(raw_ir)
    projection = project_run_receipt_v4(raw_ir, receipt)
    vector = _validate_resource_vector(resources)

    epoch = epoch_identity(
        epoch_index=epoch_index,
        computation_hash=identity.identity_hash,
        input_state_hash=input_state_hash,
        authority_hash=authority_hash,
        previous_continuation_hash=previous_continuation_hash,
    )
    continuation = continuation_receipt(
        epoch=epoch,
        result_hash=_projection_hash(projection, "result_hash"),
        state_hash=_projection_hash(projection, "state_hash"),
        observations_hash=_projection_hash(projection, "observation_transcript_hash"),
        effects_hash=_projection_hash(projection, "effect_receipt_hash"),
        resources_hash=vector.vector_hash,
    )
    return epoch, continuation


def _normalize_r2_receipt(
    value: Any,
) -> tuple[ProgramIRV4EffectsR2PlanReceipt, dict[str, Any] | None]:
    if isinstance(value, ProgramIRV4EffectsR2PlanResult):
        return value.receipt, dict(value.plan_artifact)
    if isinstance(value, ProgramIRV4EffectsR2PlanReceipt):
        return value, None
    _fail(
        "TEVS_OMEGA_V2_RECEIPT",
        "Effects R2 projection requires ProgramIRV4EffectsR2PlanResult or its exact receipt",
    )


def _require_exact_receipt(value: Any, expected: Any, expected_type: type, profile: str) -> None:
    if not isinstance(value, expected_type):
        _fail("TEVS_OMEGA_V2_RECEIPT", f"{profile} projection received the wrong V2 receipt type")
    if value != expected:
        _fail("TEVS_OMEGA_V2_RECEIPT", f"{profile} receipt does not match deterministic V2 replay")


def _validate_resource_vector(value: Any) -> ResourceVectorV1:
    if not isinstance(value, ResourceVectorV1):
        _fail("TEVS_OMEGA_V2_RESOURCES", "Omega epoch requires ResourceVectorV1")
    wire = omega_wire(value)
    if not isinstance(wire, dict):
        _fail("TEVS_OMEGA_V2_RESOURCES", "Omega resource vector wire form must be an object")
    declared = wire.pop("vector_hash", None)
    if declared != omega_hash(wire):
        _fail("TEVS_OMEGA_V2_RESOURCES", "Omega resource vector hash mismatch")
    return value


def _projection_hash(value: Mapping[str, object], field: str) -> str:
    raw = value.get(field)
    if not isinstance(raw, str):
        _fail("TEVS_OMEGA_V2_PROJECTION", f"projection field {field!r} is not a hash")
    return raw


def _absent_hash(kind: str) -> str:
    return omega_hash({"schema": ABSENT_SCHEMA, "kind": kind})


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
