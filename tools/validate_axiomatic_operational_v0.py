from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = (
    "spec/TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0.md",
    "formal/smt/tev_script_operational_axioms_v0.smt2",
    "formal/smt/tev_script_effect_negative_control_v0.smt2",
    "formal/repotalk/TEVScriptOperationalAxiomsV0.campaign.json",
    "tools/validate_axiomatic_system_correspondence_v0.py",
)


def validate() -> tuple[str, ...]:
    failures: list[str] = []
    for relative in REQUIRED:
        if not (ROOT / relative).is_file():
            failures.append("missing:" + relative)

    layers = ROOT / "spec/TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0.md"
    if layers.is_file():
        text = layers.read_text(encoding="utf-8")
        for layer in range(9):
            if f"## L{layer} " not in text:
                failures.append(f"layers:missing:L{layer}")
        for token in (
            "Field + Transformation",
            "Canonical determinism",
            "Deterministic compilation",
            "Closed-transition determinism",
            "No implicit effect",
            "Paraconsistent object logic",
            "Resource non-negativity",
            "Admission before selection",
            "Exact distribution identity",
        ):
            if token not in text:
                failures.append("layers:missing_token:" + token)

    smt = ROOT / "formal/smt/tev_script_operational_axioms_v0.smt2"
    if smt.is_file():
        text = smt.read_text(encoding="utf-8")
        if text.count("(check-sat)") != 7:
            failures.append("smt:operational_check_count")
        for token in (
            "CommitEffect",
            "HasCapability",
            "ResourceUpperKnown",
            "VerifiedReceipt",
            "SameClosedInput",
            "ExplicitExternalDifference",
        ):
            if token not in text:
                failures.append("smt:operational_missing:" + token)

    negative = ROOT / "formal/smt/tev_script_effect_negative_control_v0.smt2"
    if negative.is_file():
        text = negative.read_text(encoding="utf-8")
        if text.count("(check-sat)") != 1:
            failures.append("smt:effect_negative_check_count")
        if "CommitEffect -> HasCapability" not in text:
            failures.append("smt:effect_negative_explanation")

    campaign_path = ROOT / "formal/repotalk/TEVScriptOperationalAxiomsV0.campaign.json"
    if campaign_path.is_file():
        try:
            campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("campaign:invalid_json")
            campaign = {}
        if campaign.get("schema") != "TEV_SCRIPT_REPOTALK_OPERATIONAL_FORMAL_CAMPAIGN_V0":
            failures.append("campaign:schema")
        if campaign.get("status") != "PREPARED_NOT_EXECUTED":
            failures.append("campaign:status")
        if campaign.get("tool") != "repotalk_formal_verify":
            failures.append("campaign:tool")
        if campaign.get("expected_head_sha_runtime_required") is not True:
            failures.append("campaign:exact_head")
        tasks = {
            row.get("id"): row
            for row in campaign.get("tasks", [])
            if isinstance(row, dict)
        }
        expected = {
            "Z3_OPERATIONAL_THEOREMS": (
                "formal/smt/tev_script_operational_axioms_v0.smt2",
                "unsat",
                False,
                7,
            ),
            "Z3_EFFECT_NEGATIVE_CONTROL": (
                "formal/smt/tev_script_effect_negative_control_v0.smt2",
                "unsat",
                True,
                1,
            ),
        }
        if set(tasks) != set(expected):
            failures.append("campaign:task_set")
        for task_id, (source, outcome, negative_control, count) in expected.items():
            row = tasks.get(task_id, {})
            if row.get("engine") != "z3":
                failures.append(f"campaign:{task_id}:engine")
            if row.get("source_path") != source:
                failures.append(f"campaign:{task_id}:source")
            if row.get("expected_outcome") != outcome:
                failures.append(f"campaign:{task_id}:outcome")
            if row.get("negative_control") is not negative_control:
                failures.append(f"campaign:{task_id}:negative")
            if row.get("required_observed_count") != count:
                failures.append(f"campaign:{task_id}:count")
        negative_row = tasks.get("Z3_EFFECT_NEGATIVE_CONTROL", {})
        if negative_row.get("required_negative_control_witness") != "EXPECTED_OUTCOME_REJECTED":
            failures.append("campaign:negative_witness")

    manifest_path = ROOT / "spec/TEV_SCRIPT_AXIOM_OBLIGATIONS_V0.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            failures.append("manifest:invalid_json")
            manifest = {}
        if manifest.get("system_layer_spec") != "spec/TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0.md":
            failures.append("manifest:system_layer_spec")
        operational = {
            row.get("id"): row
            for row in manifest.get("operational_formal_sources", [])
            if isinstance(row, dict)
        }
        if set(operational) != {"Z3_OPERATIONAL_THEOREMS", "Z3_EFFECT_NEGATIVE_CONTROL"}:
            failures.append("manifest:operational_sources")
        repotalk = manifest.get("repotalk")
        if not isinstance(repotalk, dict) or repotalk.get("operational_campaign_path") != "formal/repotalk/TEVScriptOperationalAxiomsV0.campaign.json":
            failures.append("manifest:operational_campaign")
        promotion = manifest.get("promotion")
        if not isinstance(promotion, dict) or promotion.get("requires_repotalk_operational_z3") is not True:
            failures.append("manifest:operational_promotion_gate")

    for relative in (
        "CANONICAL_INDEX.json",
        "spec/TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json",
    ):
        path = ROOT / relative
        if path.is_file() and "TEV_SCRIPT_AXIOMATIC_SYSTEM_LAYERS_V0" in path.read_text(encoding="utf-8"):
            failures.append("authority:premature_binding:" + relative)

    return tuple(sorted(set(failures)))


def main() -> int:
    failures = validate()
    if failures:
        for failure in failures:
            print("TEV_SCRIPT_AXIOMATIC_OPERATIONAL_V0=FAIL:" + failure)
        return 1
    print("TEV_SCRIPT_AXIOMATIC_OPERATIONAL_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
