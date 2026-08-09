from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "unity" / "Package"
RUNTIME = PACKAGE / "Runtime" / "Unity"
TESTS = PACKAGE / "Tests" / "PlayMode"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def csharp_brace_balance(text: str) -> int:
    balance = 0
    index = 0
    state = "code"
    escaped = False
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if state == "code":
            if current == '"':
                state = "string"
            elif current == "'":
                state = "character"
            elif current == "/" and following == "/":
                state = "line_comment"
                index += 1
            elif current == "/" and following == "*":
                state = "block_comment"
                index += 1
            elif current == "{":
                balance += 1
            elif current == "}":
                balance -= 1
                require(balance >= 0, "csharp_unexpected_closing_brace")
        elif state in {"string", "character"}:
            closing = '"' if state == "string" else "'"
            if escaped:
                escaped = False
            elif current == "\\":
                escaped = True
            elif current == closing:
                state = "code"
        elif state == "line_comment":
            if current == "\n":
                state = "code"
        elif state == "block_comment":
            if current == "*" and following == "/":
                state = "code"
                index += 1
        index += 1
    require(state in {"code", "line_comment"}, f"csharp_lexical_state:{state}")
    return balance


def main() -> int:
    unity_asm = load_json(RUNTIME / "Marcbeacve.TevScript.Unity.asmdef")
    require(unity_asm.get("name") == "Marcbeacve.TevScript.Unity", "unity_asm_name")
    require(unity_asm.get("references") == ["Marcbeacve.TevScript.Core"], "unity_asm_references")
    require(unity_asm.get("allowUnsafeCode") is False, "unity_asm_unsafe")
    require(unity_asm.get("noEngineReferences") is False, "unity_asm_engine_boundary")

    test_asm = load_json(TESTS / "Marcbeacve.TevScript.Tests.PlayMode.asmdef")
    require(
        test_asm.get("references") == [
            "Marcbeacve.TevScript.Core",
            "Marcbeacve.TevScript.Unity",
        ],
        "playmode_test_references",
    )
    require(test_asm.get("includePlatforms") == [], "playmode_test_platform")
    require(test_asm.get("defineConstraints") == ["UNITY_INCLUDE_TESTS"], "playmode_test_constraint")
    require(test_asm.get("optionalUnityReferences") == ["TestAssemblies"], "playmode_test_framework")

    runtime_text = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted(RUNTIME.glob("*.cs"))
    )
    test_text = (TESTS / "TevScriptUnityPlayModeGateTests.cs").read_text(encoding="utf-8")

    require("using System.Numerics;" not in test_text, "playmode_test_system_numerics_namespace_ambiguous")
    require("using BigInteger = System.Numerics.BigInteger;" in test_text, "playmode_test_big_integer_alias_missing")

    for path in list(sorted(RUNTIME.glob("*.cs"))) + [TESTS / "TevScriptUnityPlayModeGateTests.cs"]:
        require(csharp_brace_balance(path.read_text(encoding="utf-8")) == 0, f"brace_mismatch:{path.name}")

    require("UnityEditor" not in runtime_text, "unity_editor_leaked_into_runtime_adapter")
    require("Animator" not in runtime_text, "animator_outside_gate2_scope")
    require("UnityEngine.AnimationModule" not in runtime_text, "animation_module_outside_gate2_scope")
    forbidden_discovery = (
        "FindObjectOfType",
        "FindFirstObjectByType",
        "FindAnyObjectByType",
        "GameObject.Find",
        "GetComponent<",
    )
    for token in forbidden_discovery:
        require(token not in runtime_text, f"implicit_authority_discovery:{token}")

    required_runtime_tokens = (
        'CapabilityId => "input.move2d"',
        'CapabilityId => "motion.move2d"',
        'CapabilityId => "animation.play"',
        'CapabilityId => "time.delta"',
        'CapabilityId => "debug.log"',
        "FloatToRatExact",
        "RatToFloat",
        "TEVS_UNITY_FLOAT_NONFINITE",
        "TEVS_UNITY_RAT_FLOAT_RANGE",
        "Time.deltaTime",
        "target.position",
        "Debug.Log",
        "TevScriptAnimationStateSink",
    )
    for token in required_runtime_tokens:
        require(token in runtime_text, f"runtime_token_missing:{token}")

    required_test_markers = (
        "UNITY_PLAYMODE_ACTIVE=PASS",
        "UNITY_CAPABILITY_INPUT_MOVE2D=PASS",
        "UNITY_CAPABILITY_MOTION_TRANSFORM2D=PASS",
        "UNITY_CAPABILITY_ANIMATION_PLAY=PASS",
        "UNITY_CAPABILITY_DEBUG_LOG=PASS",
        "UNITY_CAPABILITY_TIME_DELTA=PASS",
        "UNITY_FLOAT_TO_RAT_EXACT=PASS",
        "UNITY_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS",
        "UNITY_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS",
        "UNITY_NONFINITE_FLOAT_FAIL_CLOSED=PASS",
        "TEV_SCRIPT_UNITY_PLAYMODE_GATE_2=PASS",
    )
    for marker in required_test_markers:
        require(marker in test_text, f"test_marker_missing:{marker}")

    fixture = TESTS / "Resources" / "TevScriptGate2Player.json"
    canonical = ROOT / "examples" / "Player.tevs.ir.json"
    require(fixture.is_file(), "playmode_player_fixture_missing")
    require(canonical.is_file(), "canonical_player_fixture_missing")
    require(fixture.read_bytes() == canonical.read_bytes(), "playmode_player_fixture_drift")

    print("UNITY_GATE2_RUNTIME_ASSEMBLY=PASS")
    print("UNITY_GATE2_PLAYMODE_TEST_ASSEMBLY=PASS")
    print("UNITY_GATE2_EXPLICIT_AUTHORITY=PASS")
    print("UNITY_GATE2_ANIMATOR_DEPENDENCY=ABSENT_BY_SCOPE")
    print("UNITY_GATE2_FLOAT_BOUNDARY_STATIC=PASS")
    print("UNITY_GATE2_PLAYER_FIXTURE_IDENTITY=PASS")
    print("UNITY_GATE2_INPUT_SYSTEM_DEVICE=NOT_PROBED")
    print("UNITY_GATE2_ANIMATOR_CONTROLLER=NOT_PROBED")
    print("TEV_SCRIPT_UNITY_PLAYMODE_GATE2_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
