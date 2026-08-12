from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json

AXIOMATIC_FORMAL_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_AXIOMATIC_FORMAL_RECEIPT_V0"

_HEX = frozenset("0123456789abcdef")
_STABLE = re.compile(r"^[A-Za-z0-9_.:/+\-]+$")
_RESULT_IDS = frozenset(
    {
        "LEAN_ABSTRACT_THEORY",
        "Z3_THEOREMS",
        "Z3_NONCOLLAPSE_MODEL",
        "Z3_SELECTION_NEGATIVE_CONTROL",
        "Z3_OPERATIONAL_THEOREMS",
        "Z3_EFFECT_NEGATIVE_CONTROL",
    }
)
_REQUIRED_VERIFICATION = frozenset(
    {
        "axiomatic_semantics_static",
        "axiomatic_system_correspondence",
        "axiomatic_operational",
        "axiomatic_closed_coverage",
        "axiomatic_evidence_contract",
        "repotalk_lean",
        "repotalk_z3_semantic",
        "repotalk_z3_operational",
        "tevprover_structural_replay",
    }
)
_ROOT_FIELDS = frozenset(
    {
        "schema",
        "status",
        "source",
        "artifact_hashes",
        "repotalk_result_hashes",
        "tevprover",
        "verification",
        "authority",
        "receipt_hash",
    }
)
_SOURCE_FIELDS = frozenset({"branch", "head", "tree"})
_TEVPROVER_FIELDS = frozenset(
    {
        "proof_file_sha256",
        "proof_object_sha256",
        "result_document_sha256",
        "certified_scope",
    }
)
_AUTHORITY_FIELDS = frozenset(
    {
        "semantic_authority",
        "truth_authority",
        "write_authority",
        "promotion_authority",
    }
)


class AxiomaticFormalReceiptError(ValueError):
    pass


def _mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise AxiomaticFormalReceiptError(what + " must be an object")
    result = dict(value)
    canonical_json(result)
    return result


def _fields(value: Mapping[str, object], expected: frozenset[str], what: str) -> None:
    observed = set(value)
    if observed != expected:
        raise AxiomaticFormalReceiptError(
            f"{what} field set mismatch missing={sorted(expected - observed)} "
            f"extra={sorted(observed - expected)}"
        )


def _hash64(value: object, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise AxiomaticFormalReceiptError(what)
    return text


def _git_hash40(value: object, what: str) -> str:
    text = str(value).lower()
    if len(text) != 40 or any(char not in _HEX for char in text):
        raise AxiomaticFormalReceiptError(what)
    return text


def _stable(value: object, what: str) -> str:
    text = str(value)
    if not text or _STABLE.fullmatch(text) is None:
        raise AxiomaticFormalReceiptError(what)
    return text


def _hash_map(value: object, what: str) -> dict[str, str]:
    mapping = _mapping(value, what)
    if not mapping:
        raise AxiomaticFormalReceiptError(what + " must not be empty")
    result: dict[str, str] = {}
    for key, digest in mapping.items():
        stable_key = _stable(key, what + " key")
        result[stable_key] = _hash64(digest, what + " sha256")
    return dict(sorted(result.items()))


def _scope(value: object) -> dict[str, object]:
    scope = _mapping(value, "tevprover certified_scope")
    required = {
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
    for key, expected in required.items():
        if scope.get(key) != expected:
            raise AxiomaticFormalReceiptError(
                "tevprover certified scope mismatch: " + key
            )
    if scope.get("boundary_violation") not in {None, ""}:
        raise AxiomaticFormalReceiptError(
            "tevprover certified scope boundary violation"
        )
    return scope


@dataclass(frozen=True, slots=True)
class AxiomaticFormalReceiptV0:
    document: Mapping[str, object]

    def __post_init__(self) -> None:
        root = _mapping(self.document, "axiomatic formal receipt")
        _fields(root, _ROOT_FIELDS, "axiomatic formal receipt")
        if root["schema"] != AXIOMATIC_FORMAL_RECEIPT_SCHEMA_V0:
            raise AxiomaticFormalReceiptError("axiomatic formal receipt schema")
        if root["status"] != "PASS":
            raise AxiomaticFormalReceiptError("axiomatic formal receipt status")

        source = _mapping(root["source"], "source")
        _fields(source, _SOURCE_FIELDS, "source")
        _stable(source["branch"], "source branch")
        _git_hash40(source["head"], "source head")
        _git_hash40(source["tree"], "source tree")

        artifacts = _hash_map(root["artifact_hashes"], "artifact_hashes")
        required_artifacts = {
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
        }
        if set(artifacts) != required_artifacts:
            raise AxiomaticFormalReceiptError("axiomatic artifact set mismatch")

        repotalk = _hash_map(
            root["repotalk_result_hashes"],
            "repotalk_result_hashes",
        )
        if set(repotalk) != _RESULT_IDS:
            raise AxiomaticFormalReceiptError("RepoTalk result set mismatch")

        tevprover = _mapping(root["tevprover"], "tevprover")
        _fields(tevprover, _TEVPROVER_FIELDS, "tevprover")
        proof_file_hash = _hash64(
            tevprover["proof_file_sha256"],
            "tevprover proof file sha256",
        )
        _hash64(
            tevprover["proof_object_sha256"],
            "tevprover canonical proof object sha256",
        )
        _hash64(
            tevprover["result_document_sha256"],
            "tevprover result document sha256",
        )
        _scope(tevprover["certified_scope"])
        proof_path = "formal/tevprover/TEVScriptFourValueV0.proof.json"
        if artifacts[proof_path] != proof_file_hash:
            raise AxiomaticFormalReceiptError(
                "tevprover proof file hash is not bound to axiomatic artifact"
            )

        verification = _mapping(root["verification"], "verification")
        if set(verification) != _REQUIRED_VERIFICATION:
            raise AxiomaticFormalReceiptError("verification field set mismatch")
        for key in _REQUIRED_VERIFICATION:
            if verification[key] != "PASS":
                raise AxiomaticFormalReceiptError(
                    "required axiomatic verification is not PASS: " + key
                )

        authority = _mapping(root["authority"], "authority")
        _fields(authority, _AUTHORITY_FIELDS, "authority")
        if any(authority.values()):
            raise AxiomaticFormalReceiptError(
                "axiomatic receipt authority escalation"
            )

        receipt_hash = _hash64(root["receipt_hash"], "receipt_hash")
        body = {
            key: value for key, value in root.items() if key != "receipt_hash"
        }
        if canonical_hash(body) != receipt_hash:
            raise AxiomaticFormalReceiptError(
                "axiomatic receipt canonical hash mismatch"
            )
        object.__setattr__(self, "document", root)

    @property
    def receipt_hash(self) -> str:
        return str(self.document["receipt_hash"])

    @property
    def source_head(self) -> str:
        return str(_mapping(self.document["source"], "source")["head"])

    @property
    def source_tree(self) -> str:
        return str(_mapping(self.document["source"], "source")["tree"])

    def to_object(self) -> dict[str, object]:
        return dict(self.document)


def build_axiomatic_formal_receipt_v0(
    *,
    branch: str,
    head: str,
    tree: str,
    artifact_hashes: Mapping[str, str],
    repotalk_result_hashes: Mapping[str, str],
    tevprover_proof_file_sha256: str,
    tevprover_proof_object_sha256: str,
    tevprover_result_document_sha256: str,
    tevprover_certified_scope: Mapping[str, object],
) -> AxiomaticFormalReceiptV0:
    body: dict[str, object] = {
        "schema": AXIOMATIC_FORMAL_RECEIPT_SCHEMA_V0,
        "status": "PASS",
        "source": {
            "branch": branch,
            "head": head,
            "tree": tree,
        },
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "repotalk_result_hashes": dict(sorted(repotalk_result_hashes.items())),
        "tevprover": {
            "proof_file_sha256": tevprover_proof_file_sha256,
            "proof_object_sha256": tevprover_proof_object_sha256,
            "result_document_sha256": tevprover_result_document_sha256,
            "certified_scope": dict(tevprover_certified_scope),
        },
        "verification": {
            key: "PASS" for key in sorted(_REQUIRED_VERIFICATION)
        },
        "authority": {
            "semantic_authority": False,
            "truth_authority": False,
            "write_authority": False,
            "promotion_authority": False,
        },
    }
    return AxiomaticFormalReceiptV0(
        {**body, "receipt_hash": canonical_hash(body)}
    )


def verify_axiomatic_formal_receipt_v0(
    receipt: Mapping[str, object],
    *,
    expected_receipt_hash: str,
    expected_source_head: str,
    expected_source_tree: str,
) -> AxiomaticFormalReceiptV0:
    parsed = AxiomaticFormalReceiptV0(receipt)
    if parsed.receipt_hash != _hash64(
        expected_receipt_hash,
        "expected axiomatic receipt hash",
    ):
        raise AxiomaticFormalReceiptError("axiomatic receipt identity mismatch")
    if parsed.source_head != _git_hash40(
        expected_source_head,
        "expected source head",
    ):
        raise AxiomaticFormalReceiptError(
            "axiomatic receipt source head mismatch"
        )
    if parsed.source_tree != _git_hash40(
        expected_source_tree,
        "expected source tree",
    ):
        raise AxiomaticFormalReceiptError(
            "axiomatic receipt source tree mismatch"
        )
    return parsed


__all__ = [
    "AXIOMATIC_FORMAL_RECEIPT_SCHEMA_V0",
    "AxiomaticFormalReceiptError",
    "AxiomaticFormalReceiptV0",
    "build_axiomatic_formal_receipt_v0",
    "verify_axiomatic_formal_receipt_v0",
]
