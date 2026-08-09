from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .linked_program_v1 import LinkedProgramBundleV1
from .lowering_ir_v3_linked_v1 import LinkedV1IrV3Bundle


@dataclass(frozen=True, slots=True)
class LoweringReceiptBundleV2:
    receipt: dict[str, object]
    canonical_json: str
    receipt_hash: str


def build_ir_v3_lowering_receipt(
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV3Bundle,
) -> LoweringReceiptBundleV2:
    _verify_source(source)
    _verify_target(target, source.semantic_hash)
    if target.linked_semantic_hash != source.semantic_hash:
        raise TevScriptError(
            "TEVS_V1_IRV3_RECEIPT_SOURCE_MISMATCH",
            "IR V3 bundle is bound to a different linked semantic hash",
        )

    body: dict[str, object] = {
        "schema":"TEV_SCRIPT_LOWERING_RECEIPT_V2",
        "profile":"TEV_SCRIPT_V1_TO_IR_V3_FULL_PROFILE_V1",
        "source":{
            "schema":"TEV_SCRIPT_LINKED_PROGRAM_V1",
            "language_version":"1.0.0",
            "semantic_hash":source.semantic_hash,
            "artifact_sha256":_sha256_text(source.canonical_json),
        },
        "target":{
            "schema":"TEV_SCRIPT_PROGRAM_IR_V3",
            "language_version":"1.0.0",
            "lowering_profile":"TEV_SCRIPT_V1_IR_V3_PROFILE_V1",
            "source_semantic_hash":str(target.ir["source_semantic_hash"]),
            "semantic_hash":str(target.ir["semantic_hash"]),
            "artifact_sha256":_sha256_text(target.canonical_json),
        },
        "proof_obligations":{
            "source_semantic_hash_verified":True,
            "source_hash_embedded_in_target":True,
            "target_ir_v3_contract_validated":True,
            "closed_runtime_type_table_validated":True,
            "algebraic_value_types_preserved":True,
            "forward_only_cfg_validated":True,
        },
    }
    receipt_hash = canonical_hash(body)
    receipt = dict(body)
    receipt["receipt_hash"] = receipt_hash
    return LoweringReceiptBundleV2(receipt, canonical_json(receipt), receipt_hash)


def verify_ir_v3_lowering_receipt(
    receipt: Mapping[str, object],
    source: LinkedProgramBundleV1,
    target: LinkedV1IrV3Bundle,
) -> None:
    _verify_source(source)
    _verify_target(target, source.semantic_hash)
    expected_fields = {"schema","profile","source","target","proof_obligations","receipt_hash"}
    if set(receipt) != expected_fields:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_FIELDS", "lowering receipt V2 field set mismatch")
    if receipt.get("schema") != "TEV_SCRIPT_LOWERING_RECEIPT_V2":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_SCHEMA", "invalid lowering receipt V2 schema")
    if receipt.get("profile") != "TEV_SCRIPT_V1_TO_IR_V3_FULL_PROFILE_V1":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_PROFILE", "invalid V1-to-IR-V3 lowering profile")
    raw_hash = receipt.get("receipt_hash")
    if not isinstance(raw_hash, str):
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_HASH", "receipt hash must be text")
    body = {key:value for key,value in receipt.items() if key != "receipt_hash"}
    if canonical_hash(body) != raw_hash:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_HASH", "receipt hash mismatch")
    expected = build_ir_v3_lowering_receipt(source, target).receipt
    if canonical_json(dict(receipt)) != canonical_json(expected):
        raise TevScriptError(
            "TEVS_V1_IRV3_RECEIPT_BINDING",
            "receipt does not bind supplied linked source and IR V3 target exactly",
        )


def _verify_source(source: LinkedProgramBundleV1) -> None:
    program = source.program
    if program.get("schema") != "TEV_SCRIPT_LINKED_PROGRAM_V1" or program.get("language_version") != "1.0.0":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_SOURCE", "unexpected linked source schema/version")
    semantic = {key:value for key,value in program.items() if key != "semantic_hash"}
    if program.get("semantic_hash") != source.semantic_hash or canonical_hash(semantic) != source.semantic_hash:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_SOURCE_HASH", "linked source semantic hash mismatch")
    if canonical_json(program) != source.canonical_json:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_SOURCE_BYTES", "linked source canonical bytes mismatch")


def _verify_target(target: LinkedV1IrV3Bundle, source_hash: str) -> None:
    validate_program_ir_v3(target.ir, expected_source_semantic_hash=source_hash)
    if target.ir.get("schema") != "TEV_SCRIPT_PROGRAM_IR_V3":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_SCHEMA", "unexpected target schema")
    if target.ir.get("language_version") != "1.0.0":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_VERSION", "unexpected target language version")
    if target.ir.get("lowering_profile") != "TEV_SCRIPT_V1_IR_V3_PROFILE_V1":
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_PROFILE", "unexpected target lowering profile")
    if target.ir.get("source_semantic_hash") != source_hash:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_SOURCE_HASH", "target source hash mismatch")
    if target.linked_semantic_hash != source_hash:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_BINDING", "target bundle linked hash mismatch")
    if canonical_json(target.ir) != target.canonical_json:
        raise TevScriptError("TEVS_V1_IRV3_RECEIPT_TARGET_BYTES", "target canonical bytes mismatch")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
