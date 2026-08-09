from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .ir_validation import validate_program_ir
from .linked_program_v1 import LinkedProgramBundleV1
from .lowering_ir_v2_linked_v1 import LinkedV1IrV2Bundle


@dataclass(frozen=True, slots=True)
class LoweringReceiptBundleV1:
    receipt: dict[str, object]
    canonical_json: str
    receipt_hash: str


def build_ir_v2_lowering_receipt(
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV2Bundle,
) -> LoweringReceiptBundleV1:
    """Bind one canonical V1 linked program to its validated IR V2 image.

    The receipt is not a second semantic hash. It is an evidence object binding
    source semantic identity, target IR semantic identity and exact canonical
    artifact bytes under the explicitly restricted erasable lowering profile.
    """
    _verify_source_bundle(source)
    _verify_target_bundle(target)
    if target.linked_semantic_hash != source.semantic_hash:
        raise TevScriptError(
            "TEVS_V1_LOWER_RECEIPT_SOURCE_MISMATCH",
            "target lowering bundle is bound to a different linked-program semantic hash",
        )

    body: dict[str, object] = {
        "schema": "TEV_SCRIPT_LOWERING_RECEIPT_V1",
        "profile": "TEV_SCRIPT_V1_TO_IR_V2_ERASABLE_PROFILE_V1",
        "source": {
            "schema": "TEV_SCRIPT_LINKED_PROGRAM_V1",
            "language_version": "1.0.0",
            "semantic_hash": source.semantic_hash,
            "artifact_sha256": _sha256_text(source.canonical_json),
        },
        "target": {
            "schema": "TEV_SCRIPT_PROGRAM_IR_V2",
            "language_version": "0.2.0",
            "semantic_hash": str(target.ir["semantic_hash"]),
            "artifact_sha256": _sha256_text(target.canonical_json),
        },
        "proof_obligations": {
            "source_semantic_hash_verified": True,
            "ir_v2_lowering_boundary_clear": True,
            "target_ir_contract_validated": True,
            "runtime_v1_value_kinds_erased": True,
        },
    }
    receipt_hash = canonical_hash(body)
    receipt = dict(body)
    receipt["receipt_hash"] = receipt_hash
    return LoweringReceiptBundleV1(
        receipt=receipt,
        canonical_json=canonical_json(receipt),
        receipt_hash=receipt_hash,
    )


def verify_ir_v2_lowering_receipt(
    receipt: Mapping[str, object],
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV2Bundle,
) -> None:
    _verify_source_bundle(source)
    _verify_target_bundle(target)

    required = {
        "schema",
        "profile",
        "source",
        "target",
        "proof_obligations",
        "receipt_hash",
    }
    if set(receipt) != required:
        raise TevScriptError(
            "TEVS_V1_LOWER_RECEIPT_FIELDS",
            f"lowering receipt field set mismatch: {sorted(receipt)}",
        )
    if receipt.get("schema") != "TEV_SCRIPT_LOWERING_RECEIPT_V1":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SCHEMA", "invalid lowering receipt schema")
    if receipt.get("profile") != "TEV_SCRIPT_V1_TO_IR_V2_ERASABLE_PROFILE_V1":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_PROFILE", "invalid lowering profile")

    raw_hash = receipt.get("receipt_hash")
    if not isinstance(raw_hash, str):
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_HASH", "receipt hash must be text")
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    if canonical_hash(body) != raw_hash:
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_HASH", "receipt hash mismatch")

    expected = build_ir_v2_lowering_receipt(source, target).receipt
    if canonical_json(dict(receipt)) != canonical_json(expected):
        raise TevScriptError(
            "TEVS_V1_LOWER_RECEIPT_BINDING",
            "receipt does not bind the supplied source and target artifacts exactly",
        )


def _verify_source_bundle(source: LinkedProgramBundleV1) -> None:
    program = source.program
    if program.get("schema") != "TEV_SCRIPT_LINKED_PROGRAM_V1":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SOURCE_SCHEMA", "unexpected source schema")
    if program.get("language_version") != "1.0.0":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SOURCE_VERSION", "unexpected source language version")
    if program.get("semantic_hash") != source.semantic_hash:
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SOURCE_HASH", "source bundle semantic hash mismatch")
    semantic = {key: value for key, value in program.items() if key != "semantic_hash"}
    if canonical_hash(semantic) != source.semantic_hash:
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SOURCE_HASH", "source semantic object was modified")
    if canonical_json(program) != source.canonical_json:
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_SOURCE_BYTES", "source canonical bytes mismatch")


def _verify_target_bundle(target: LinkedV1IrV2Bundle) -> None:
    validate_program_ir(target.ir)
    if target.ir.get("schema") != "TEV_SCRIPT_PROGRAM_IR_V2":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_TARGET_SCHEMA", "unexpected target schema")
    if target.ir.get("language_version") != "0.2.0":
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_TARGET_VERSION", "unexpected target language version")
    if canonical_json(target.ir) != target.canonical_json:
        raise TevScriptError("TEVS_V1_LOWER_RECEIPT_TARGET_BYTES", "target canonical bytes mismatch")


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
