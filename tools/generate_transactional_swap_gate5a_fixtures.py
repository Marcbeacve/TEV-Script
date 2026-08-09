from __future__ import annotations

import copy
import hashlib
import json
import re
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
            "CANONICAL_DEBUG_HASH_RECONSTRUCTION_FAILED "
            f"expected={program['debug_hash']} observed={observed_debug}"
        )
    observed_semantic = digest(semantic_view(program))
    if observed_semantic != program["semantic_hash"]:
        raise RuntimeError(
            "CANONICAL_SEMANTIC_HASH_RECONSTRUCTION_FAILED "
            f"expected={program['semantic_hash']} observed={observed_semantic}"
        )


def refresh_semantic(program: dict) -> None:
    program["semantic_hash"] = digest(semantic_view(program))


def mutate_valid_initial(value):
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 17
    if isinstance(value, str):
        # Exact integers/rationals may be represented textually in some
        # value encodings. Keep the mutation conservative.
        try:
            return str(int(value) + 17)
        except ValueError:
            return value + "_gate5"
    if isinstance(value, list):
        if not value:
            return value
        result = copy.deepcopy(value)
        result[0] = mutate_valid_initial(result[0])
        return result
    if isinstance(value, dict):
        result = copy.deepcopy(value)
        # Preserve the encoding shape and mutate the first scalar leaf.
        for key in sorted(result):
            changed = mutate_valid_initial(result[key])
            if changed != result[key]:
                result[key] = changed
                return result
        return result
    raise RuntimeError(
        f"UNSUPPORTED_INITIAL_ENCODING={type(value).__name__}"
    )


def write(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    base_path = Path(args.base)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    base = json.loads(base_path.read_text(encoding="utf-8"))
    verify_hashes(base)

    if not base.get("entities"):
        raise RuntimeError("BASE_PROGRAM_HAS_NO_ENTITIES")
    first_entity = base["entities"][0]
    states = first_entity.get("states", [])
    if not states:
        raise RuntimeError("BASE_PROGRAM_HAS_NO_STATES")

    # Good candidate:
    # - same program/entity identity
    # - same existing state names/types
    # - changes an existing initial value, proving migration overrides it
    # - adds one new state, proving additive state initialization
    good = copy.deepcopy(base)
    good_first = good["entities"][0]
    original_state = good_first["states"][0]
    original_state["initial"] = mutate_valid_initial(
        original_state["initial"]
    )
    added = copy.deepcopy(original_state)
    added["name"] = "__gate5_added"
    # Ensure the newly added state's initial differs from the currently
    # running snapshot in a deterministic way.
    added["initial"] = mutate_valid_initial(added["initial"])
    good_first["states"].append(added)
    refresh_semantic(good)
    verify_hashes(good)
    if good["semantic_hash"] == base["semantic_hash"]:
        raise RuntimeError("GOOD_CANDIDATE_HASH_DID_NOT_CHANGE")

    # Negative: remove the additive, unreferenced state from the good
    # candidate. This remains a valid IR, but when the good candidate is
    # active the transactional continuity layer must reject the removal.
    removed = copy.deepcopy(good)
    removed_states = removed["entities"][0]["states"]
    removed_states[:] = [
        state for state in removed_states
        if state.get("name") != "__gate5_added"
    ]
    if len(removed_states) == len(good["entities"][0]["states"]):
        raise RuntimeError("GATE5_ADDITIVE_STATE_NOT_REMOVED")
    refresh_semantic(removed)
    verify_hashes(removed)

    # Negative: capability authority escalation. Derive from the good
    # candidate so state continuity passes and the rejection reaches the
    # explicit capability-ceiling layer.
    escalated = copy.deepcopy(good)
    capabilities = escalated["entities"][0].get("capabilities", [])
    if not capabilities:
        raise RuntimeError("BASE_PROGRAM_HAS_NO_CAPABILITIES")
    extra_capability = copy.deepcopy(capabilities[0])
    extra_capability["capability_id"] = "gate5.unapproved"
    capabilities.append(extra_capability)
    refresh_semantic(escalated)
    verify_hashes(escalated)

    # Negative: identity discontinuity while remaining a valid IR.
    # program_id uses the Identifier grammar:
    # [A-Za-z_][A-Za-z0-9_]*
    # Derive from good so only program identity is intentionally different.
    wrong_program = copy.deepcopy(good)
    wrong_program["program_id"] = (
        str(wrong_program["program_id"]) + "_Gate5Invalid"
    )
    if not re.fullmatch(
        r"[A-Za-z_][A-Za-z0-9_]*",
        wrong_program["program_id"],
    ):
        raise RuntimeError(
            "GATE5_PROGRAM_ID_NEGATIVE_NOT_IDENTIFIER"
        )
    if wrong_program["program_id"] == good["program_id"]:
        raise RuntimeError(
            "GATE5_PROGRAM_ID_NEGATIVE_DID_NOT_CHANGE"
        )
    refresh_semantic(wrong_program)
    verify_hashes(wrong_program)

    write(out / "candidate.good.json", good)
    write(out / "candidate.state_removed.json", removed)
    write(out / "candidate.capability_escalated.json", escalated)
    write(out / "candidate.program_id_changed.json", wrong_program)

    print("GATE5A_CANONICAL_HASH_RECONSTRUCTION=PASS")
    print("GATE5A_GOOD_CANDIDATE_GENERATION=PASS")
    print("GATE5A_NEGATIVE_STATE_REMOVAL_VALID_IR=GENERATED")
    print("GATE5A_NEGATIVE_CAPABILITY_ESCALATION=GENERATED")
    print("GATE5A_NEGATIVE_PROGRAM_ID_VALID_IR=GENERATED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
