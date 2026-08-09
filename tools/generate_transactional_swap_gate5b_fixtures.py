from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def digest(value) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def semantic_view(program: dict) -> dict:
    return {
        key: value
        for key, value in program.items()
        if key not in ("semantic_hash", "debug", "debug_hash")
    }


def verify_hashes(program: dict) -> None:
    observed_debug = digest(program["debug"])
    if observed_debug != program["debug_hash"]:
        raise RuntimeError(
            "GATE5B_DEBUG_HASH_INVALID "
            f"expected={program['debug_hash']} observed={observed_debug}"
        )
    observed_semantic = digest(semantic_view(program))
    if observed_semantic != program["semantic_hash"]:
        raise RuntimeError(
            "GATE5B_SEMANTIC_HASH_INVALID "
            f"expected={program['semantic_hash']} observed={observed_semantic}"
        )


def refresh_semantic(program: dict) -> None:
    program["semantic_hash"] = digest(semantic_view(program))


def write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def find_damage_handler(program: dict) -> dict:
    for entity in program["entities"]:
        if entity.get("entity_id") != "Player":
            continue
        for handler in entity.get("handlers", []):
            if handler.get("event_id") == "damage":
                return handler
    raise RuntimeError("GATE5B_DAMAGE_HANDLER_MISSING")


def mutate_damage_to_noop(program: dict) -> None:
    handler = find_damage_handler(program)
    matches = []
    for index, instruction in enumerate(handler["instructions"]):
        if (
            instruction.get("op") == "LOAD_PARAM"
            and instruction.get("name") == "amount"
            and instruction.get("type") == "Int"
        ):
            matches.append(index)
    if len(matches) != 1:
        raise RuntimeError(
            f"GATE5B_DAMAGE_AMOUNT_LOAD_COUNT={len(matches)}"
        )
    handler["instructions"][matches[0]] = {
        "op": "CONST",
        "type": "Int",
        "value": {"$int": "0"},
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--gate5a-dir", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base_path = Path(args.base)
    gate5a_dir = Path(args.gate5a_dir)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    base = json.loads(base_path.read_text(encoding="utf-8"))
    verify_hashes(base)

    gate5a_good = json.loads(
        (gate5a_dir / "candidate.good.json").read_text(encoding="utf-8")
    )
    verify_hashes(gate5a_good)

    good = copy.deepcopy(gate5a_good)
    mutate_damage_to_noop(good)
    refresh_semantic(good)
    verify_hashes(good)

    if good["program_id"] != base["program_id"]:
        raise RuntimeError("GATE5B_GOOD_PROGRAM_ID_DRIFT")
    if good["semantic_hash"] == base["semantic_hash"]:
        raise RuntimeError("GATE5B_GOOD_SEMANTIC_HASH_DID_NOT_CHANGE")

    # Valid-IR state-removal negative while GOOD is active.
    removed = copy.deepcopy(good)
    states = removed["entities"][0]["states"]
    before_count = len(states)
    states[:] = [
        state for state in states
        if state.get("name") != "__gate5_added"
    ]
    if len(states) != before_count - 1:
        raise RuntimeError("GATE5B_ADDITIVE_STATE_REMOVAL_FAILED")
    refresh_semantic(removed)
    verify_hashes(removed)

    # Valid-IR authority escalation negative.
    escalated = copy.deepcopy(good)
    capabilities = escalated["entities"][0].get("capabilities", [])
    if not capabilities:
        raise RuntimeError("GATE5B_BASE_CAPABILITIES_MISSING")
    extra = copy.deepcopy(capabilities[0])
    extra["capability_id"] = "gate5b.unapproved"
    capabilities.append(extra)
    refresh_semantic(escalated)
    verify_hashes(escalated)

    # Valid-IR program-id discontinuity negative.
    wrong_program = copy.deepcopy(good)
    wrong_program["program_id"] = (
        str(wrong_program["program_id"]) + "_Gate5BInvalid"
    )
    refresh_semantic(wrong_program)
    verify_hashes(wrong_program)

    write(out / "base.json", base)
    write(out / "candidate.good.json", good)
    write(out / "candidate.state_removed.json", removed)
    write(out / "candidate.capability_escalated.json", escalated)
    write(out / "candidate.program_id_changed.json", wrong_program)

    print("GATE5B_BASE_HASH_RECONSTRUCTION=PASS")
    print("GATE5B_GATE5A_GOOD_INPUT_VALID=PASS")
    print("GATE5B_UPDATED_BEHAVIOR_IR=GENERATED")
    print("GATE5B_STATE_REMOVAL_VALID_IR=GENERATED")
    print("GATE5B_CAPABILITY_ESCALATION_VALID_IR=GENERATED")
    print("GATE5B_PROGRAM_ID_NEGATIVE_VALID_IR=GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
