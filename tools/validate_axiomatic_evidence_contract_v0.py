from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "tev_script/axiomatic_formal_receipt_v0.py",
    "RUN_TEV_SCRIPT_AXIOMATIC_PREFLIGHT_V0.py",
    "RUN_TEV_SCRIPT_AXIOMATIC_FORMAL_ADMISSION_V0.py",
    "tools/validate_axiomatic_formal_evidence_v0.py",
    "tests/test_axiomatic_formal_receipt_v0.py",
    "tests/test_axiomatic_formal_evidence_v0.py",
)

TEVPROVER_PUBLIC_PROOF_PORT = "tevprover_cuofc.verify_proof"


def _campaign(
    relative: str,
    *,
    schema: str,
    failures: list[str],
) -> None:
    path = ROOT / relative
    if not path.is_file():
        failures.append("campaign:missing:" + relative)
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        failures.append("campaign:invalid_json:" + relative)
        return
    if data.get("schema") != schema:
        failures.append("campaign:schema:" + relative)
    if data.get("status") != "PREPARED_NOT_EXECUTED":
        failures.append("campaign:status:" + relative)
    if data.get("tool") != "repotalk_formal_verify":
        failures.append("campaign:tool:" + relative)
    if data.get("source_mode") != "REPOTALK_REMOTE_EXACT_REPOSITORY":
        failures.append("campaign:source_mode:" + relative)
    if data.get("repository") != "Marcbeacve/TEV-Script":
        failures.append("campaign:repository:" + relative)
    if data.get("local_root_for_certification_allowed") is not False:
        failures.append("campaign:local_root:" + relative)
    if data.get("expected_head_sha_runtime_required") is not True:
        failures.append("campaign:head_binding:" + relative)
    if data.get("expected_tree_sha_bound_by_remote_receipt") is not True:
        failures.append("campaign:tree_binding:" + relative)
    versions = data.get("expected_tool_versions")
    if not isinstance(versions, dict) or versions.get("z3") != "4.16.0":
        failures.append("campaign:z3_version:" + relative)
    if relative.endswith("TEVScriptAxiomsV0.campaign.json"):
        if versions.get("lean") != "4.32.2":
            failures.append("campaign:lean_version:" + relative)
        if data.get("lean_toolchain_tree_hash_required") is not True:
            failures.append("campaign:lean_tree_hash:" + relative)


def validate() -> tuple[str, ...]:
    failures: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            failures.append("missing:" + relative)

    receipt = ROOT / "tev_script/axiomatic_formal_receipt_v0.py"
    if receipt.is_file():
        text = receipt.read_text(encoding="utf-8")
        for token in (
            "TEV_SCRIPT_AXIOMATIC_FORMAL_RECEIPT_V0",
            "proof_file_sha256",
            "proof_object_sha256",
            "result_document_sha256",
            "repotalk_result_hashes",
            "axiomatic_evidence_contract",
            "tevprover_structural_replay",
            "semantic_authority",
            "promotion_authority",
            "canonical_hash(body)",
        ):
            if token not in text:
                failures.append("receipt:missing_token:" + token)

    evidence = ROOT / "tools/validate_axiomatic_formal_evidence_v0.py"
    if evidence.is_file():
        text = evidence.read_text(encoding="utf-8")
        for token in (
            "repotalk.formal-verification/v1",
            "repotalk.remote-workspace-materialization/v1",
            "TEVPROVER_VERIFICATION_RESULT_V1",
            "EXPECTED_OUTCOME_REJECTED",
            "persistent_effect_absence",
            "source_witness_sha256",
            "hash_bound",
            "tree_hash_bound",
            "commit_sha",
            "tree_sha",
            "accepted_by_kernel",
            "STRUCTURAL_CHECK",
            "proof_file_sha256",
        ):
            if token not in text:
                failures.append("evidence:missing_token:" + token)

    admission = ROOT / "RUN_TEV_SCRIPT_AXIOMATIC_FORMAL_ADMISSION_V0.py"
    if admission.is_file():
        text = admission.read_text(encoding="utf-8")
        for token in (
            '_git("status", "--porcelain")',
            "requires a clean checkout",
            "receipt output must be outside repository",
            "TEV_SCRIPT_AXIOMATIC_FORMAL_ADMISSION_V0=PASS",
        ):
            if token not in text:
                failures.append("admission:missing_token:" + token)

    _campaign(
        "formal/repotalk/TEVScriptAxiomsV0.campaign.json",
        schema="TEV_SCRIPT_REPOTALK_FORMAL_CAMPAIGN_V0",
        failures=failures,
    )
    _campaign(
        "formal/repotalk/TEVScriptOperationalAxiomsV0.campaign.json",
        schema="TEV_SCRIPT_REPOTALK_OPERATIONAL_FORMAL_CAMPAIGN_V0",
        failures=failures,
    )

    manifest_path = ROOT / "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("manifest:invalid_json")
            manifest = {}
        formal_receipt = manifest.get("formal_evidence_receipt")
        if not isinstance(formal_receipt, dict):
            failures.append("manifest:formal_evidence_receipt")
        else:
            if (
                formal_receipt.get("schema")
                != "TEV_SCRIPT_AXIOMATIC_FORMAL_RECEIPT_V0"
            ):
                failures.append("manifest:receipt_schema")
            if (
                formal_receipt.get("status")
                != "BLOCKED_ON_FORMAL_EXECUTION"
            ):
                failures.append("manifest:receipt_status")
            if formal_receipt.get(
                "artifact_file_hash_distinct_from_canonical_proof_hash"
            ) is not True:
                failures.append("manifest:dual_proof_identity")
        repotalk = manifest.get("repotalk")
        if not isinstance(repotalk, dict):
            failures.append("manifest:repotalk")
        else:
            if (
                repotalk.get("certification_source_mode")
                != "REPOTALK_REMOTE_EXACT_REPOSITORY"
            ):
                failures.append("manifest:repotalk_source_mode")
            if repotalk.get("lean_toolchain_tree_hash_required") is not True:
                failures.append("manifest:lean_tree_hash")
        tevprover = manifest.get("tevprover")
        if not isinstance(tevprover, dict):
            failures.append("manifest:tevprover")
        elif tevprover.get("installed_port") != TEVPROVER_PUBLIC_PROOF_PORT:
            failures.append("manifest:tevprover_public_proof_port")
        promotion = manifest.get("promotion")
        if not isinstance(promotion, dict) or promotion.get(
            "requires_axiomatic_formal_receipt"
        ) is not True:
            failures.append("manifest:formal_receipt_promotion_gate")

    tevprover_plan_path = ROOT / "formal/tevprover/TEVScriptAxiomsV0.plan.json"
    if not tevprover_plan_path.is_file():
        failures.append("tevprover_plan:missing")
    else:
        try:
            tevprover_plan = json.loads(
                tevprover_plan_path.read_text(encoding="utf-8")
            )
        except json.JSONDecodeError:
            failures.append("tevprover_plan:invalid_json")
            tevprover_plan = {}
        if tevprover_plan.get("installed_port") != TEVPROVER_PUBLIC_PROOF_PORT:
            failures.append("tevprover_plan:public_proof_port")
        if tevprover_plan.get("semantic_authority") is not False:
            failures.append("tevprover_plan:semantic_authority")

    for relative in (
        "CANONICAL_INDEX.json",
        "spec/TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json",
    ):
        path = ROOT / relative
        if (
            path.is_file()
            and "TEV_SCRIPT_AXIOMATIC_FORMAL_RECEIPT_V0"
            in path.read_text(encoding="utf-8")
        ):
            failures.append(
                "authority:premature_formal_receipt_binding:" + relative
            )

    return tuple(sorted(set(failures)))


def main() -> int:
    failures = validate()
    if failures:
        for failure in failures:
            print(
                "TEV_SCRIPT_AXIOMATIC_EVIDENCE_CONTRACT_V0=FAIL:"
                + failure
            )
        return 1
    print("TEV_SCRIPT_AXIOMATIC_EVIDENCE_CONTRACT_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
