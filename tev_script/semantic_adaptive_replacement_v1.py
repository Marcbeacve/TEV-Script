from __future__ import annotations

from dataclasses import dataclass
from copy import deepcopy
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .conformance import run_conformance
from .runtime import ScriptRuntime
from .semantic_kernel_v0 import SemanticFieldV0, field_from_mapping
from .semantic_residual_v0 import ResidualObstructionV0, residual_from_obstructions
from .values import decode_typed_value, encode_typed_value

ADAPTIVE_REPLACEMENT_CANARY_BUNDLE_SCHEMA_V1 = "TEV_SCRIPT_ADAPTIVE_REPLACEMENT_CANARY_BUNDLE_V1"
ADAPTIVE_REPLACEMENT_PROJECTION_SCHEMA_V1 = "TEV_SCRIPT_ADAPTIVE_REPLACEMENT_CONFORMANCE_PROJECTION_V1"
ADAPTIVE_REPLACEMENT_EVALUATION_SCHEMA_V1 = "TEV_SCRIPT_ADAPTIVE_REPLACEMENT_EVALUATION_V1"

_INTERLEAVINGS = frozenset({"SERIALIZED", "IRRECOVERABLE"})
_STABLE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_HEX = frozenset("0123456789abcdef")
_BUNDLE_KEYS = frozenset(
    {
        "schema",
        "candidate_realization_hash",
        "lane_id",
        "scenario_id",
        "program_semantic_hash",
        "baseline_state",
        "baseline_state_hash",
        "interleaving",
        "capability_bindings",
        "invocations",
        "observed_final_states",
        "observed_emitted_events",
        "observed_capability_trace",
        "bundle_hash",
    }
)


class AdaptiveReplacementSemanticsError(ValueError):
    pass


def _hash64(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in _HEX for char in value)


def _stable(value: Any) -> bool:
    return isinstance(value, str) and _STABLE.fullmatch(value) is not None


def _canonical_copy(value: Any, what: str) -> Any:
    result = deepcopy(value)
    try:
        canonical_json(result)
    except Exception as error:
        raise AdaptiveReplacementSemanticsError(f"{what} must be canonicalizable") from error
    return result


@dataclass(frozen=True, slots=True)
class AdaptiveReplacementIssueV1:
    kind: str
    severity: str
    subject: str
    detail: Mapping[str, Any]

    def __post_init__(self) -> None:
        if not _stable(self.kind):
            raise AdaptiveReplacementSemanticsError("adaptive replacement issue kind must be stable")
        if self.severity not in {"REJECT", "PROOF_REQUIRED"}:
            raise AdaptiveReplacementSemanticsError("adaptive replacement issue severity")
        subject = str(self.subject)
        if not subject:
            raise AdaptiveReplacementSemanticsError("adaptive replacement issue subject")
        object.__setattr__(self, "subject", subject)
        detail = dict(self.detail)
        canonical_json(detail)
        object.__setattr__(self, "detail", detail)

    def to_object(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "severity": self.severity,
            "subject": self.subject,
            "detail": dict(self.detail),
        }


@dataclass(frozen=True, slots=True)
class AdaptiveReplacementProjectionV1:
    bundle_record_hash: str
    claimed_bundle_hash: str
    program_semantic_hash: str
    initial_state_hash: str
    scenario: Mapping[str, Any] | None
    issues: tuple[AdaptiveReplacementIssueV1, ...]

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    @property
    def scenario_hash(self) -> str:
        return "" if self.scenario is None else canonical_hash(dict(self.scenario))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ADAPTIVE_REPLACEMENT_PROJECTION_SCHEMA_V1,
            "status": self.status,
            "bundle_record_hash": self.bundle_record_hash,
            "claimed_bundle_hash": self.claimed_bundle_hash,
            "program_semantic_hash": self.program_semantic_hash,
            "initial_state_hash": self.initial_state_hash,
            "scenario_hash": self.scenario_hash,
            "scenario": None if self.scenario is None else dict(self.scenario),
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def projection_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.adaptive_replacement_projection.v1", self.to_object())


@dataclass(frozen=True, slots=True)
class AdaptiveReplacementEvaluationV1:
    projection_hash: str
    bundle_record_hash: str
    claimed_bundle_hash: str
    program_semantic_hash: str
    runner_receipt_hash: str
    issues: tuple[AdaptiveReplacementIssueV1, ...]

    @property
    def status(self) -> str:
        if any(item.severity == "REJECT" for item in self.issues):
            return "REJECT"
        return "PROOF_REQUIRED" if self.issues else "PASS"

    def to_object(self) -> dict[str, object]:
        return {
            "schema": ADAPTIVE_REPLACEMENT_EVALUATION_SCHEMA_V1,
            "status": self.status,
            "projection_hash": self.projection_hash,
            "bundle_record_hash": self.bundle_record_hash,
            "claimed_bundle_hash": self.claimed_bundle_hash,
            "program_semantic_hash": self.program_semantic_hash,
            "runner_receipt_hash": self.runner_receipt_hash,
            "issues": [item.to_object() for item in self.issues],
        }

    @property
    def evaluation_hash(self) -> str:
        return canonical_hash(self.to_object())

    def to_field(self) -> SemanticFieldV0:
        return field_from_mapping("tev.realization.adaptive_replacement_evaluation.v1", self.to_object())


def initial_conformance_state_v1(
    ir: Mapping[str, Any],
) -> tuple[list[dict[str, object]], str]:
    """Return the exact legacy-conformance initial state witness and its hash."""
    runtime = ScriptRuntime(ir, {})
    states: list[dict[str, object]] = []
    for raw_entity in ir["entities"]:
        runtime_entity = runtime.entities[raw_entity["entity_id"]]
        states.append(
            {
                "entity_id": raw_entity["entity_id"],
                "state": {
                    name: {
                        "type": runtime_entity.state_types[name],
                        "value": encode_typed_value(
                            runtime_entity.state_types[name],
                            value,
                        ),
                    }
                    for name, value in sorted(runtime_entity.state.items())
                },
            }
        )
    return states, canonical_hash(states)


def build_adaptive_replacement_canary_bundle_v1(
    *,
    candidate_realization_hash: str,
    lane_id: str,
    scenario_id: str,
    program_semantic_hash: str,
    baseline_state: list[dict[str, object]],
    interleaving: str,
    capability_bindings: Mapping[str, Any],
    invocations: list[dict[str, object]],
    observed_final_states: list[dict[str, object]],
    observed_emitted_events: list[dict[str, object]],
    observed_capability_trace: list[dict[str, object]],
) -> dict[str, object]:
    """Build a content-addressed R10 canary observation bundle.

    This function records candidate-lane observations; it does not itself admit
    replacement. Admission is performed independently by projection/evaluation.
    """
    if not _hash64(candidate_realization_hash):
        raise AdaptiveReplacementSemanticsError("candidate_realization_hash must be lowercase SHA-256")
    if not _stable(lane_id) or not _stable(scenario_id):
        raise AdaptiveReplacementSemanticsError("lane_id and scenario_id must be stable ids")
    if not _hash64(program_semantic_hash):
        raise AdaptiveReplacementSemanticsError("program_semantic_hash must be lowercase SHA-256")
    if interleaving not in _INTERLEAVINGS:
        raise AdaptiveReplacementSemanticsError("unsupported interleaving classification")

    baseline = _canonical_copy(baseline_state, "baseline_state")
    bindings = _canonical_copy(dict(capability_bindings), "capability_bindings")
    invocation_copy = _canonical_copy(invocations, "invocations")
    final_states = _canonical_copy(observed_final_states, "observed_final_states")
    events = _canonical_copy(observed_emitted_events, "observed_emitted_events")
    trace = _canonical_copy(observed_capability_trace, "observed_capability_trace")

    body: dict[str, object] = {
        "schema": ADAPTIVE_REPLACEMENT_CANARY_BUNDLE_SCHEMA_V1,
        "candidate_realization_hash": candidate_realization_hash,
        "lane_id": lane_id,
        "scenario_id": scenario_id,
        "program_semantic_hash": program_semantic_hash,
        "baseline_state": baseline,
        "baseline_state_hash": canonical_hash(baseline),
        "interleaving": interleaving,
        "capability_bindings": bindings,
        "invocations": invocation_copy,
        "observed_final_states": final_states,
        "observed_emitted_events": events,
        "observed_capability_trace": trace,
    }
    return {**body, "bundle_hash": canonical_hash(body)}


def _issue(kind: str, severity: str, subject: Any, **detail: Any) -> AdaptiveReplacementIssueV1:
    return AdaptiveReplacementIssueV1(kind, severity, str(subject), detail)


def _projection(
    *,
    bundle: Mapping[str, Any],
    ir: Mapping[str, Any],
    initial_state_hash: str,
    scenario: Mapping[str, Any] | None,
    issues: list[AdaptiveReplacementIssueV1],
) -> AdaptiveReplacementProjectionV1:
    return AdaptiveReplacementProjectionV1(
        bundle_record_hash=canonical_hash(dict(bundle)),
        claimed_bundle_hash=str(bundle.get("bundle_hash", "")),
        program_semantic_hash=str(ir.get("semantic_hash", "")),
        initial_state_hash=initial_state_hash,
        scenario=None if scenario is None else _canonical_copy(dict(scenario), "projected scenario"),
        issues=tuple(issues),
    )


def _entity_capability_contracts(ir: Mapping[str, Any], entity_id: str) -> dict[str, dict[str, Any]] | None:
    for raw_entity in ir["entities"]:
        if raw_entity["entity_id"] == entity_id:
            return {str(item["capability_id"]): dict(item) for item in raw_entity["capabilities"]}
    return None


def project_adaptive_replacement_conformance_v1(
    ir: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> AdaptiveReplacementProjectionV1:
    """Project an R10 canary bundle into the existing conformance runner.

    V1 projection is intentionally fail-closed: hot baselines, variable
    observations and irreversible interleavings cannot become false PASSes.
    """
    raw = _canonical_copy(dict(bundle), "adaptive replacement bundle")
    initial_state, initial_state_hash = initial_conformance_state_v1(ir)
    issues: list[AdaptiveReplacementIssueV1] = []

    observed_keys = set(raw)
    if observed_keys != _BUNDLE_KEYS:
        issues.append(_issue("replacement.bundle_shape_mismatch", "REJECT", canonical_hash(raw), missing=sorted(_BUNDLE_KEYS - observed_keys), extra=sorted(observed_keys - _BUNDLE_KEYS)))
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    if raw["schema"] != ADAPTIVE_REPLACEMENT_CANARY_BUNDLE_SCHEMA_V1:
        issues.append(_issue("replacement.bundle_schema_mismatch", "REJECT", raw["schema"]))
    body = {key: value for key, value in raw.items() if key != "bundle_hash"}
    expected_bundle_hash = canonical_hash(body)
    if raw["bundle_hash"] != expected_bundle_hash:
        issues.append(_issue("replacement.bundle_integrity_mismatch", "REJECT", raw["bundle_hash"], expected=expected_bundle_hash))
    if not _hash64(raw["candidate_realization_hash"]):
        issues.append(_issue("replacement.candidate_realization_hash_invalid", "REJECT", raw["candidate_realization_hash"]))
    if not _stable(raw["lane_id"]):
        issues.append(_issue("replacement.lane_id_invalid", "REJECT", raw["lane_id"]))
    if not _stable(raw["scenario_id"]):
        issues.append(_issue("replacement.scenario_id_invalid", "REJECT", raw["scenario_id"]))
    if not _hash64(raw["program_semantic_hash"]):
        issues.append(_issue("replacement.program_hash_invalid", "REJECT", raw["program_semantic_hash"]))
    elif raw["program_semantic_hash"] != ir["semantic_hash"]:
        issues.append(_issue("replacement.program_hash_mismatch", "REJECT", raw["program_semantic_hash"], expected=ir["semantic_hash"]))

    baseline_state = raw["baseline_state"]
    baseline_state_hash = raw["baseline_state_hash"]
    if not _hash64(baseline_state_hash):
        issues.append(_issue("replacement.baseline_state_hash_invalid", "REJECT", baseline_state_hash))
    else:
        observed_baseline_hash = canonical_hash(baseline_state)
        if observed_baseline_hash != baseline_state_hash:
            issues.append(_issue("replacement.baseline_state_integrity_mismatch", "REJECT", baseline_state_hash, observed=observed_baseline_hash))
        elif canonical_json(baseline_state) != canonical_json(initial_state):
            issues.append(_issue("replacement.baseline_restore_required", "PROOF_REQUIRED", baseline_state_hash, conformance_initial_state_hash=initial_state_hash))

    interleaving = raw["interleaving"]
    if interleaving not in _INTERLEAVINGS:
        issues.append(_issue("replacement.interleaving_invalid", "REJECT", interleaving))
    elif interleaving == "IRRECOVERABLE":
        issues.append(_issue("replacement.interleaving_recovery_required", "PROOF_REQUIRED", raw["bundle_hash"]))

    invocations = raw["invocations"]
    if not isinstance(invocations, list) or not invocations:
        issues.append(_issue("replacement.invocations_invalid", "REJECT", raw["bundle_hash"]))
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    invocation_entities: set[str] = set()
    invocation_shape_valid = True
    for index, invocation in enumerate(invocations):
        if not isinstance(invocation, dict) or set(invocation) != {"entity_id", "event_id", "arguments"}:
            issues.append(_issue("replacement.invocation_shape_invalid", "REJECT", index))
            invocation_shape_valid = False
            continue
        entity_id = invocation["entity_id"]
        event_id = invocation["event_id"]
        arguments = invocation["arguments"]
        if not _stable(entity_id) or not _stable(event_id) or not isinstance(arguments, list):
            issues.append(_issue("replacement.invocation_value_invalid", "REJECT", index))
            invocation_shape_valid = False
            continue
        invocation_entities.add(str(entity_id))

    if not invocation_shape_valid:
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)
    if len(invocation_entities) != 1:
        issues.append(_issue("replacement.multi_entity_projection_required", "PROOF_REQUIRED", raw["bundle_hash"], entities=sorted(invocation_entities)))
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    entity_id = next(iter(invocation_entities))
    contracts = _entity_capability_contracts(ir, entity_id)
    if contracts is None:
        issues.append(_issue("replacement.entity_unknown", "REJECT", entity_id))
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    bindings = raw["capability_bindings"]
    if not isinstance(bindings, dict):
        issues.append(_issue("replacement.capability_bindings_invalid", "REJECT", raw["bundle_hash"]))
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    binding_ids = set(bindings)
    contract_ids = set(contracts)
    for capability_id in sorted(binding_ids - contract_ids):
        issues.append(_issue("replacement.capability_undeclared", "REJECT", capability_id))
    for capability_id in sorted(contract_ids - binding_ids):
        issues.append(_issue("replacement.capability_binding_missing", "PROOF_REQUIRED", capability_id))

    projected_bindings: dict[str, object] = {}
    for capability_id in sorted(binding_ids & contract_ids):
        config = bindings[capability_id]
        contract = contracts[capability_id]
        if not isinstance(config, dict) or "mode" not in config:
            issues.append(_issue("replacement.capability_binding_invalid", "REJECT", capability_id))
            continue
        mode = config["mode"]
        return_type = str(contract["return_type"])
        kind = str(contract["kind"])

        if mode == "variable":
            issues.append(_issue("replacement.variable_observation_projection_required", "PROOF_REQUIRED", capability_id, return_type=return_type, capability_kind=kind))
            continue
        if mode == "constant":
            if set(config) != {"mode", "value_type", "value"}:
                issues.append(_issue("replacement.constant_binding_shape_invalid", "REJECT", capability_id))
                continue
            if kind != "observation" or return_type == "Unit":
                issues.append(_issue("replacement.constant_binding_not_observation", "REJECT", capability_id, capability_kind=kind, return_type=return_type))
                continue
            if config["value_type"] != return_type:
                issues.append(_issue("replacement.capability_return_type_mismatch", "REJECT", capability_id, expected=return_type, observed=config["value_type"]))
                continue
            try:
                decode_typed_value(return_type, config["value"])
            except Exception as error:
                issues.append(_issue("replacement.capability_return_value_invalid", "REJECT", capability_id, error_type=type(error).__name__))
                continue
            projected_bindings[capability_id] = deepcopy(config)
            continue
        if mode == "trace":
            if set(config) != {"mode"}:
                issues.append(_issue("replacement.trace_binding_shape_invalid", "REJECT", capability_id))
                continue
            if kind != "effect" or return_type != "Unit":
                issues.append(_issue("replacement.trace_binding_not_unit_effect", "REJECT", capability_id, capability_kind=kind, return_type=return_type))
                continue
            projected_bindings[capability_id] = {"mode": "trace"}
            continue
        issues.append(_issue("replacement.capability_mode_unknown", "REJECT", capability_id, mode=mode))

    if issues:
        return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=None, issues=issues)

    scenario = {
        "schema": "TEV_SCRIPT_CONFORMANCE_SCENARIO_V1",
        "scenario_id": raw["scenario_id"],
        "program": f"adaptive-replacement:{raw['candidate_realization_hash']}",
        "entity_id": entity_id,
        "capabilities": projected_bindings,
        "invocations": deepcopy(invocations),
    }
    return _projection(bundle=raw, ir=ir, initial_state_hash=initial_state_hash, scenario=scenario, issues=[])


def evaluate_adaptive_replacement_canary_v1(
    ir: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> AdaptiveReplacementEvaluationV1:
    projection = project_adaptive_replacement_conformance_v1(ir, bundle)
    issues = list(projection.issues)
    runner_receipt_hash = ""
    if projection.status == "PASS":
        assert projection.scenario is not None
        try:
            receipt = run_conformance(ir, projection.scenario)
        except Exception as error:
            issues.append(_issue("replacement.conformance_runner_rejected", "REJECT", projection.scenario_hash, error_type=type(error).__name__, error=str(error)))
        else:
            runner_receipt_hash = str(receipt["receipt_hash"])
            for receipt_key, bundle_key in (
                ("final_states", "observed_final_states"),
                ("emitted_events", "observed_emitted_events"),
                ("capability_trace", "observed_capability_trace"),
            ):
                if canonical_json(receipt[receipt_key]) != canonical_json(bundle[bundle_key]):
                    issues.append(_issue("replacement.observable_divergence", "REJECT", bundle_key, runner_receipt_hash=runner_receipt_hash))

    return AdaptiveReplacementEvaluationV1(
        projection_hash=projection.projection_hash,
        bundle_record_hash=projection.bundle_record_hash,
        claimed_bundle_hash=projection.claimed_bundle_hash,
        program_semantic_hash=projection.program_semantic_hash,
        runner_receipt_hash=runner_receipt_hash,
        issues=tuple(issues),
    )


def residual_from_adaptive_replacement_v1(evaluation: AdaptiveReplacementEvaluationV1) -> SemanticFieldV0:
    return residual_from_obstructions(
        domain="adaptive_safe_replacement",
        judgment_id="r10_canary_replacement",
        judgment={"kind": "candidate_may_replace_baseline", "evaluation_hash": evaluation.evaluation_hash, "status": evaluation.status},
        source={"kind": "adaptive_replacement_evaluation", "evaluation_hash": evaluation.evaluation_hash},
        obstructions=(
            ResidualObstructionV0(
                item.kind,
                item.subject,
                "resolved",
                item.severity,
                dict(item.detail),
                dependency_refs=(evaluation.bundle_record_hash, evaluation.projection_hash),
            )
            for item in evaluation.issues
        ),
    )


__all__ = [
    "ADAPTIVE_REPLACEMENT_CANARY_BUNDLE_SCHEMA_V1",
    "ADAPTIVE_REPLACEMENT_PROJECTION_SCHEMA_V1",
    "ADAPTIVE_REPLACEMENT_EVALUATION_SCHEMA_V1",
    "AdaptiveReplacementSemanticsError",
    "AdaptiveReplacementIssueV1",
    "AdaptiveReplacementProjectionV1",
    "AdaptiveReplacementEvaluationV1",
    "initial_conformance_state_v1",
    "build_adaptive_replacement_canary_bundle_v1",
    "project_adaptive_replacement_conformance_v1",
    "evaluate_adaptive_replacement_canary_v1",
    "residual_from_adaptive_replacement_v1",
]
