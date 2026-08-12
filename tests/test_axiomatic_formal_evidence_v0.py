from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tools.validate_axiomatic_formal_evidence_v0 import (
    REPOTALK_RESULTS,
    validate_evidence_dir,
)

ROOT = Path(__file__).resolve().parents[1]
HEAD = "1" * 40
TREE = "2" * 40


def _write(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ),
        encoding="utf-8",
    )


def _source_witness(source_path: str) -> dict[str, object]:
    payload = (ROOT / source_path).read_bytes()
    return {
        "path": source_path,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "byte_count": len(payload),
        "content_returned": False,
    }


def _tool_witness(engine: str) -> dict[str, object]:
    if engine == "lean":
        return {
            "engine": "lean",
            "executable_name": "lean.exe",
            "sha256": "3" * 64,
            "version": "Lean (version 4.32.2, x86_64-windows, commit test)",
            "hash_bound": True,
            "tree_root_name": "lean-4.32.2",
            "tree_sha256": "4" * 64,
            "tree_entry_count": 1,
            "tree_hash_bound": True,
        }
    return {
        "engine": "z3",
        "executable_name": "z3.exe",
        "sha256": "5" * 64,
        "version": "Z3 version 4.16.0 - 64 bit",
        "hash_bound": True,
        "tree_root_name": "",
        "tree_sha256": "",
        "tree_entry_count": 0,
        "tree_hash_bound": False,
    }


def _remote_source() -> dict[str, object]:
    return {
        "schema": "repotalk.remote-workspace-materialization/v1",
        "repository": "Marcbeacve/TEV-Script",
        "requested_ref": "realization-semantics-r0",
        "commit_sha": HEAD,
        "tree_sha": TREE,
        "host_authenticated_fetch": True,
        "sandbox_received_credentials": False,
        "remote_removed_before_execution": True,
        "checkout_persisted": False,
        "workspace_topology": "WINDOWS_VOLUME_ROOT",
        "materialization_total_ms": 1.0,
        "fetch": {},
        "checkout": {},
        "execution_authority": {"test_double": True},
    }


def _repotalk_result(
    *,
    result_id: str,
    source_path: str,
    expected_outcome: str | None,
    negative_control: bool,
    count: int,
) -> dict[str, object]:
    engine = "lean" if result_id == "LEAN_ABSTRACT_THEORY" else "z3"
    if engine == "lean":
        observed: list[str] = []
        outcome_match = True
        negative_witness = None
    elif negative_control:
        observed = ["sat"] * count
        outcome_match = False
        negative_witness = "EXPECTED_OUTCOME_REJECTED"
    else:
        assert expected_outcome is not None
        observed = [expected_outcome] * count
        outcome_match = True
        negative_witness = None
    return {
        "schema": "repotalk.formal-verification/v1",
        "status": "PASS",
        "engine": engine,
        "source_path": source_path,
        "expected_outcome": expected_outcome,
        "negative_control": negative_control,
        "negative_control_witness": negative_witness,
        "observed_outcomes": observed,
        "outcome_match": outcome_match,
        "blockers": [],
        "warnings": [],
        "source": _source_witness(source_path),
        "persistent_effect": {
            "reported": False,
            "source_persistent_effect": False,
            "absence_proved": True,
        },
        "tool": _tool_witness(engine),
        "execution": {"remote_source": _remote_source()},
    }


def _proof_hash() -> str:
    proof = json.loads(
        (
            ROOT / "formal/tevprover/TEVScriptFourValueV0.proof.json"
        ).read_text(encoding="utf-8")
    )
    payload = json.dumps(
        proof,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


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


def _materialize_evidence(directory: Path) -> None:
    for result_id, row in REPOTALK_RESULTS.items():
        filename, source_path, expected, negative, count = row
        _write(
            directory / filename,
            _repotalk_result(
                result_id=result_id,
                source_path=source_path,
                expected_outcome=expected,
                negative_control=negative,
                count=count,
            ),
        )
    _write(
        directory / "tevprover_four_value.json",
        {
            "schema": "TEVPROVER_VERIFICATION_RESULT_V1",
            "status": "accepted_by_kernel",
            "reason": "finite_relation_graph_verified",
            "proof_object_sha256": _proof_hash(),
            "certified_scope": _scope(),
            "truth_authority_bool": False,
            "write_authority_bool": False,
            "document_truth_authority_bool": False,
        },
    )


def test_axiomatic_formal_evidence_admits_complete_bound_set(tmp_path: Path) -> None:
    _materialize_evidence(tmp_path)
    failures, receipt = validate_evidence_dir(
        tmp_path,
        root=ROOT,
        branch="realization-semantics-r0",
        head=HEAD,
        tree=TREE,
    )
    assert failures == ()
    assert receipt is not None
    assert receipt.source_head == HEAD
    assert receipt.source_tree == TREE


def test_axiomatic_formal_evidence_rejects_source_witness_tamper(
    tmp_path: Path,
) -> None:
    _materialize_evidence(tmp_path)
    path = tmp_path / "repotalk_z3_theorems.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["source"]["sha256"] = "0" * 64
    _write(path, value)
    failures, receipt = validate_evidence_dir(
        tmp_path,
        root=ROOT,
        branch="realization-semantics-r0",
        head=HEAD,
        tree=TREE,
    )
    assert receipt is None
    assert any("source_witness_sha256" in item for item in failures)


def test_axiomatic_formal_evidence_rejects_wrong_remote_head(
    tmp_path: Path,
) -> None:
    _materialize_evidence(tmp_path)
    path = tmp_path / "repotalk_lean.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["execution"]["remote_source"]["commit_sha"] = "9" * 40
    _write(path, value)
    failures, receipt = validate_evidence_dir(
        tmp_path,
        root=ROOT,
        branch="realization-semantics-r0",
        head=HEAD,
        tree=TREE,
    )
    assert receipt is None
    assert any("remote_source:commit_sha" in item for item in failures)


def test_axiomatic_formal_evidence_rejects_unbound_lean_tree(
    tmp_path: Path,
) -> None:
    _materialize_evidence(tmp_path)
    path = tmp_path / "repotalk_lean.json"
    value = json.loads(path.read_text(encoding="utf-8"))
    value["tool"]["tree_hash_bound"] = False
    _write(path, value)
    failures, receipt = validate_evidence_dir(
        tmp_path,
        root=ROOT,
        branch="realization-semantics-r0",
        head=HEAD,
        tree=TREE,
    )
    assert receipt is None
    assert any(
        "lean_toolchain_tree_not_hash_bound" in item for item in failures
    )
