from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "unity" / "PlayerGates" / "IL2CPP"
RUNTIME = GATE / "Runtime"
EDITOR = GATE / "Editor"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    runtime_asm = load_json(
        RUNTIME / "Marcbeacve.TevScript.Gate4.Il2CppPlayer.asmdef"
    )
    require(
        runtime_asm.get("name") ==
        "Marcbeacve.TevScript.Gate4.Il2CppPlayer",
        "gate4_runtime_asm_name",
    )
    require(
        runtime_asm.get("references") == [
            "Marcbeacve.TevScript.Core",
            "Marcbeacve.TevScript.Unity",
        ],
        "gate4_runtime_asm_references",
    )
    require(
        runtime_asm.get("includePlatforms") == [],
        "gate4_runtime_platforms",
    )
    require(
        runtime_asm.get("autoReferenced") is False,
        "gate4_runtime_auto_reference",
    )

    editor_asm = load_json(
        EDITOR / "Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor.asmdef"
    )
    require(
        editor_asm.get("name") ==
        "Marcbeacve.TevScript.Gate4.Il2CppPlayer.Editor",
        "gate4_editor_asm_name",
    )
    require(
        editor_asm.get("references") == [
            "Marcbeacve.TevScript.Gate4.Il2CppPlayer"
        ],
        "gate4_editor_asm_references",
    )
    require(
        editor_asm.get("includePlatforms") == ["Editor"],
        "gate4_editor_platform",
    )

    runtime = (
        RUNTIME / "TevScriptIl2CppPlayerGate.cs"
    ).read_text(encoding="utf-8")
    builder = (
        EDITOR / "TevScriptIl2CppPlayerBuildGate.cs"
    ).read_text(encoding="utf-8")
    runner = (
        ROOT / "RUN_TEV_SCRIPT_UNITY_IL2CPP_PLAYER_CONFORMANCE_V1.ps1"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "FindObjectOfType",
        "FindFirstObjectByType",
        "FindAnyObjectByType",
        "GameObject.Find",
        "GetComponent<",
        "System.Reflection",
    ):
        require(forbidden not in runtime, f"gate4_forbidden_runtime:{forbidden}")

    runtime_markers = (
        "UNITY_IL2CPP_PLAYER_ACTIVE=PASS",
        "UNITY_IL2CPP_PLAYER_PLATFORM=WINDOWS_PLAYER_PASS",
        "UNITY_IL2CPP_PLAYER_CORE_PARSE=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_DEBUG_LOG=PASS",
        "UNITY_IL2CPP_PLAYER_RUNTIME_STATE=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_TIME_DELTA=PASS",
        "UNITY_IL2CPP_PLAYER_FLOAT_TO_RAT_EXACT=PASS",
        "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_BOUNDARY_WITNESS=PASS",
        "UNITY_IL2CPP_PLAYER_TIME_DELTA_BOUNDARY_WITNESS=PASS",
        "UNITY_IL2CPP_PLAYER_RAT_TO_FLOAT_ROUNDING_EXPOSED=PASS",
        "UNITY_IL2CPP_PLAYER_NONFINITE_FLOAT_FAIL_CLOSED=PASS",
        "UNITY_IL2CPP_PLAYER_CAPABILITY_ABI=PASS",
        "UNITY_IL2CPP_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS",
        "UNITY_IL2CPP_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS",
        "TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=PASS",
    )
    for marker in runtime_markers:
        require(marker in runtime, f"gate4_runtime_marker:{marker}")

    require(
        "ScriptingImplementation.IL2CPP" in builder,
        "gate4_builder_il2cpp_backend",
    )
    require(
        "BuildTarget.StandaloneWindows64" in builder,
        "gate4_builder_windows64",
    )
    require(
        "NamedBuildTarget.Standalone" in builder,
        "gate4_builder_named_target",
    )
    for marker in (
        "UNITY_IL2CPP_PLAYER_BUILD_BACKEND=IL2CPP",
        "UNITY_IL2CPP_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64",
        "UNITY_IL2CPP_PLAYER_BUILD_RESULT=PASS",
    ):
        require(marker in builder, f"gate4_builder_marker:{marker}")

    for marker in (
        "GameAssembly.dll",
        "global-metadata.dat",
        "MonoBleedingEdge",
        "UNITY_IL2CPP_GAMEASSEMBLY=PASS",
        "UNITY_IL2CPP_GLOBAL_METADATA=PASS",
        "UNITY_IL2CPP_MONO_RUNTIME=ABSENT_PASS",
        "UNITY_IL2CPP_PLAYER_PROCESS_EXIT_CODE",
        "TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE_4=PASS",
    ):
        require(marker in runner, f"gate4_runner_marker:{marker}")

    print("UNITY_GATE4_RUNTIME_ASSEMBLY_REFERENCES=EXPLICIT_PASS")
    print("UNITY_GATE4_EDITOR_ASSEMBLY_BOUNDARY=EDITOR_ONLY_PASS")
    print("UNITY_GATE4_IL2CPP_BACKEND_STATIC=PASS")
    print("UNITY_GATE4_AOT_ARTIFACT_WITNESSES_STATIC=PASS")
    print("UNITY_GATE4_PROVIDER_AUTHORITY_STATIC=EXPLICIT_PASS")
    print("TEV_SCRIPT_UNITY_IL2CPP_PLAYER_GATE4_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
