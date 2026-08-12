from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Mapping

from tev_script.axiomatic_formal_receipt_v0 import (
    AxiomaticFormalReceiptV0,
    build_axiomatic_formal_receipt_v0,
)
from tools.validate_axiomatic_coverage_v0 import validate as validate_coverage
from tools.validate_axiomatic_evidence_contract_v0 import (
    validate as validate_evidence_contract,
)
from tools.validate_axiomatic_operational_v0 import validate as validate_operational
from tools.validate_axiomatic_semantics_v0 import validate as validate_semantics
from tools.validate_axiomatic_system_correspondence_v0 import (
    validate as validate_system_correspondence,
)

ROOT = Path(__file__).resolve().parents[1]
REPOTALK_SCHEMA = "repotalk.formal-verification/v1"
REPOTALK_REMOTE_SCHEMA = "repotalk.remote-workspace-materialization/v1"
TEVPROVER_RESULT_SCHEMA = "TEVPROVER_VERIFICATION_RESULT_V1"
REPOSITORY = "Marcbeacve/TEV-Script"
EXPECTED_TOOL_VERSIONS = {"z3": "4.16.0", "lean": "4.32.2"}
_HEX = frozenset("0123456789abcdef")

REPOTALK_RESULTS: dict[str, tuple[str, str, str | None, bool, int]] = {
    "LEAN_ABSTRACT_THEORY": (
        "repotalk_lean.json",
        "formal/lean/TEVScriptAxiomsV0.lean",
        None,
        False,
        0,
    ),
    "Z3_THEOREMS": (
        "repotalk_z3_theorems.json",
        "formal/smt/tev_script_axioms_theorems_v0.smt2",
        "unsat",
        False,
        5,
    ),
    "Z3_NONCOLLAPSE_MODEL": (
        "repotalk_z3_model.json",
        "formal/smt/tev_script_axioms_model_v0.smt2",
        "sat",
        False,
        1,
    ),
    "Z3_SELECTION_NEGATIVE_CONTROL": (
        "repotalk_z3_selection_negative.json",
        "formal/smt/tev_script_axioms_negative_control_v0.smt2",
        "unsat",
        True,
        1,
    ),
    "Z3_OPERATIONAL_THEOREMS": (
        "repotalk_z3_operational.json",
        "formal/smt/tev_script_operational_axioms_v0.smt2",
        "unsat",
        False,
        7,
    ),
    "Z3_EFFECT_NEGATIVE_CONTROL": (
        "repotalk_z3_effect_negative.json",
        "formal/smt/tev_script_effect_negative_control_v0.smt2",
        "unsat",
        True,
        1,
    ),
}

AXIOMATIC_ARTIFACTS = (
    "spec/TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0.md",
    "spec/TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0.md",
    "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json",
    "spec/TEV_SCRIPT_AXIOM_COVERAGE_V0.json",
    "formal/lean/TEVScriptAxiomsV0.lean",
    "formal/smt/tev_script_axioms_theorems_v0.smt2",
    "formal/smt/tev_script_axioms_model_v0.smt2",
    "formal/smt/tev_script_axioms_negative_control_v0.smt2",
    "formal/smt/tev_script_operational_axioms_v0.smt2",
    "formal/smt/tev_script_effect_negative_control_v0.smt2",
    "formal/tevprover/TEVScriptFourValueV0.proof.json",
)


def _sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("evidence document must be an object: " + path.name)
    return value


def _hash64(value: object) -> bool:
    text = str(value or "").lower()
    return len(text) == 64 and all(char in _HEX for char in text)


def _validate_static(root: Path) -> tuple[str, ...]:
    failures: list[str] = []
    failures.extend("semantics:" + item for item in validate_semantics(root))
    failures.extend(
        "system_correspondence:" + item
        for item in validate_system_correspondence()
    )
    failures.extend("operational:" + item for item in validate_operational())
    failures.extend("coverage:" + item for item in validate_coverage())
    failures.extend(
        "evidence_contract:" + item for item in validate_evidence_contract()
    )
    return tuple(sorted(set(failures)))


def _validate_source_witness(
    result: Mapping[str, object],
    *,
    root: Path,
    source_path: str,
) -> str | None:
    witness = result.get("source")
    if not isinstance(witness, Mapping):
        return "source_witness_missing"
    source = root / source_path
    payload = source.read_bytes()
    if witness.get("path") != source_path:
        return "source_witness_path"
    if witness.get("sha256") != hashlib.sha256(payload).hexdigest():
        return "source_witness_sha256"
    if witness.get("byte_count") != len(payload):
        return "source_witness_byte_count"
    if witness.get("content_returned") is not False:
        return "source_witness_content_returned"
    return None


def _validate_tool_witness(
    result: Mapping[str, object],
    *,
    engine: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    tool = result.get("tool")
    if not isinstance(tool, Mapping):
        return ("tool_witness_missing",)
    if tool.get("engine") != engine:
        failures.append("tool_engine")
    if tool.get("hash_bound") is not True:
        failures.append("tool_not_hash_bound")
    if not _hash64(tool.get("sha256")):
        failures.append("tool_sha256")
    if not str(tool.get("executable_name") or ""):
        failures.append("tool_executable_name")
    version = str(tool.get("version") or "")
    if EXPECTED_TOOL_VERSIONS[engine] not in version:
        failures.append("tool_version")
    if engine == "lean":
        if tool.get("tree_hash_bound") is not True:
            failures.append("lean_toolchain_tree_not_hash_bound")
        if not str(tool.get("tree_root_name") or ""):
            failures.append("lean_toolchain_tree_root_name")
        if not _hash64(tool.get("tree_sha256")):
            failures.append("lean_toolchain_tree_sha256")
        count = tool.get("tree_entry_count")
        if isinstance(count, bool) or not isinstance(count, int) or count <= 0:
            failures.append("lean_toolchain_tree_entry_count")
    return tuple(sorted(set(failures)))


def _validate_remote_source(
    result: Mapping[str, object],
    *,
    head: str,
    tree: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    execution = result.get("execution")
    if not isinstance(execution, Mapping):
        return ("execution_missing",)
    remote = execution.get("remote_source")
    if not isinstance(remote, Mapping):
        return ("remote_source_missing",)
    expected = {
        "schema": REPOTALK_REMOTE_SCHEMA,
        "repository": REPOSITORY,
        "commit_sha": head,
        "tree_sha": tree,
        "host_authenticated_fetch": True,
        "sandbox_received_credentials": False,
        "remote_removed_before_execution": True,
        "checkout_persisted": False,
    }
    for key, value in expected.items():
        if remote.get(key) != value:
            failures.append("remote_source:" + key)
    authority = remote.get("execution_authority")
    if not isinstance(authority, Mapping):
        failures.append("remote_source:execution_authority")
    return tuple(sorted(set(failures)))


def _validate_repotalk(
    result: Mapping[str, object],
    *,
    root: Path,
    result_id: str,
    source_path: str,
    expected_outcome: str | None,
    negative_control: bool,
    expected_count: int,
    head: str,
    tree: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    engine = "lean" if result_id == "LEAN_ABSTRACT_THEORY" else "z3"
    if result.get("schema") != REPOTALK_SCHEMA:
        failures.append("schema")
    if result.get("status") != "PASS":
        failures.append("status")
    if result.get("engine") != engine:
        failures.append("engine")
    if result.get("source_path") != source_path:
        failures.append("source_path")
    if result.get("expected_outcome") != expected_outcome:
        failures.append("expected_outcome")
    if result.get("negative_control") is not negative_control:
        failures.append("negative_control")
    if result.get("blockers") != []:
        failures.append("blockers")
    persistent = result.get("persistent_effect")
    if (
        not isinstance(persistent, Mapping)
        or persistent.get("absence_proved") is not True
    ):
        failures.append("persistent_effect_absence")
    source_failure = _validate_source_witness(
        result,
        root=root,
        source_path=source_path,
    )
    if source_failure:
        failures.append(source_failure)
    failures.extend(_validate_tool_witness(result, engine=engine))
    failures.extend(_validate_remote_source(result, head=head, tree=tree))

    observed = result.get("observed_outcomes")
    if not isinstance(observed, list):
        failures.append("observed_outcomes")
        observed = []
    if engine == "z3":
        if len(observed) != expected_count:
            failures.append("observed_count")
        if negative_control:
            if (
                result.get("negative_control_witness")
                != "EXPECTED_OUTCOME_REJECTED"
            ):
                failures.append("negative_control_witness")
            if result.get("outcome_match") is not False:
                failures.append("negative_control_outcome_match")
            if not observed or any(
                item == expected_outcome for item in observed
            ):
                failures.append("negative_control_not_rejected")
        else:
            if result.get("negative_control_witness") is not None:
                failures.append("unexpected_negative_control_witness")
            if result.get("outcome_match") is not True:
                failures.append("outcome_match")
            if any(item != expected_outcome for item in observed):
                failures.append("unexpected_z3_outcome")
    else:
        if result.get("negative_control_witness") is not None:
            failures.append("lean_negative_control_witness")
        if result.get("outcome_match") is not True:
            failures.append("lean_outcome_match")
        if not isinstance(result.get("warnings"), list):
            failures.append("lean_warnings_shape")

    return tuple(sorted(set(failures)))


def _validate_tevprover(
    result: Mapping[str, object],
    *,
    root: Path,
) -> tuple[str, ...]:
    failures: list[str] = []
    proof_path = root / "formal/tevprover/TEVScriptFourValueV0.proof.json"
    proof = _json(proof_path)
    expected_proof_hash = _canonical_sha256(proof)
    if result.get("schema") != TEVPROVER_RESULT_SCHEMA:
        failures.append("schema")
    if result.get("status") != "accepted_by_kernel":
        failures.append("status")
    if result.get("proof_object_sha256") != expected_proof_hash:
        failures.append("proof_object_sha256")
    for key in (
        "truth_authority_bool",
        "write_authority_bool",
        "document_truth_authority_bool",
    ):
        if result.get(key) is not False:
            failures.append("authority:" + key)
    scope = result.get("certified_scope")
    if not isinstance(scope, Mapping):
        failures.append("certified_scope")
        scope = {}
    required_scope = {
        "policy_id": "TEVPROVER_POLICY_V2",
        "frame": "TEV_NATIVE_EXACT_FINITE",
        "goal_kind": "finite_relation_graph",
        "semantic_domain": "FINITE_RELATIONAL",
        "quantification": "FINITE_WITNESS_CARRIER",
        "strength": "STRUCTURAL_CHECK",
        "external_authority_bool": False,
        "universal_claim_bool": False,
        "claim_id_semantic_authority_bool": False,
    }
    for key, expected in required_scope.items():
        if scope.get(key) != expected:
            failures.append("certified_scope:" + key)
    if scope.get("boundary_violation") not in {None, ""}:
        failures.append("certified_scope:boundary_violation")
    return tuple(sorted(set(failures)))


def validate_evidence_dir(
    evidence_dir: Path,
    *,
    root: Path = ROOT,
    branch: str,
    head: str,
    tree: str,
) -> tuple[tuple[str, ...], AxiomaticFormalReceiptV0 | None]:
    root = root.resolve()
    evidence_dir = evidence_dir.resolve()
    failures = list(_validate_static(root))
    repotalk_hashes: dict[str, str] = {}

    for result_id, row in REPOTALK_RESULTS.items():
        filename, source_path, expected, negative, count = row
        path = evidence_dir / filename
        if not path.is_file():
            failures.append("repotalk:missing:" + filename)
            continue
        try:
            document = _json(path)
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append("repotalk:invalid_json:" + filename)
            continue
        current = _validate_repotalk(
            document,
            root=root,
            result_id=result_id,
            source_path=source_path,
            expected_outcome=expected,
            negative_control=negative,
            expected_count=count,
            head=head,
            tree=tree,
        )
        failures.extend(
            f"repotalk:{result_id}:{item}" for item in current
        )
        repotalk_hashes[result_id] = _sha256_bytes(path)

    tevprover_path = evidence_dir / "tevprover_four_value.json"
    tevprover_document: dict[str, object] | None = None
    if not tevprover_path.is_file():
        failures.append("tevprover:missing:tevprover_four_value.json")
    else:
        try:
            tevprover_document = _json(tevprover_path)
        except (OSError, ValueError, json.JSONDecodeError):
            failures.append("tevprover:invalid_json")
        if tevprover_document is not None:
            failures.extend(
                "tevprover:" + item
                for item in _validate_tevprover(
                    tevprover_document,
                    root=root,
                )
            )

    if failures or tevprover_document is None:
        return tuple(sorted(set(failures))), None

    artifacts = {
        relative: _sha256_bytes(root / relative)
        for relative in AXIOMATIC_ARTIFACTS
    }
    proof_path = root / "formal/tevprover/TEVScriptFourValueV0.proof.json"
    proof = _json(proof_path)
    scope = tevprover_document["certified_scope"]
    assert isinstance(scope, Mapping)
    receipt = build_axiomatic_formal_receipt_v0(
        branch=branch,
        head=head,
        tree=tree,
        artifact_hashes=artifacts,
        repotalk_result_hashes=repotalk_hashes,
        tevprover_proof_file_sha256=_sha256_bytes(proof_path),
        tevprover_proof_object_sha256=_canonical_sha256(proof),
        tevprover_result_document_sha256=_sha256_bytes(tevprover_path),
        tevprover_certified_scope=scope,
    )
    return (), receipt


__all__ = [
    "AXIOMATIC_ARTIFACTS",
    "REPOTALK_RESULTS",
    "validate_evidence_dir",
]
