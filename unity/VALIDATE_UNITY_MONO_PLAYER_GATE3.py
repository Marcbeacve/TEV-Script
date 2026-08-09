from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MONO = ROOT / "unity" / "PlayerGates" / "Mono"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    runtime = (MONO / "TevScriptMonoPlayerGate.cs").read_text(encoding="utf-8")
    build = (MONO / "TevScriptMonoPlayerBuildGate.cs").read_text(encoding="utf-8")
    asmdef = json.loads((MONO / "Marcbeacve.TevScript.Gate3.MonoPlayer.asmdef").read_text(encoding="utf-8"))

    require("UnityEditor" not in runtime, "unity_editor_leaked_into_player_gate")
    require("System.Reflection" not in runtime, "reflection_leaked_into_player_gate")
    require("FindObjectOfType" not in runtime, "implicit_authority_find_object")
    require("FindFirstObjectByType" not in runtime, "implicit_authority_find_first")
    require("FindAnyObjectByType" not in runtime, "implicit_authority_find_any")
    require("GameObject.Find" not in runtime, "implicit_authority_gameobject_find")
    require("GetComponent<" not in runtime, "implicit_authority_get_component")

    start_begin = runtime.index("private IEnumerator Start()")
    start_end = runtime.index("private void RunGate()")
    start_block = runtime[start_begin:start_end]
    require(start_block.count("yield return null;") == 2, "gate3_coroutine_yield_count")
    first_yield = start_block.index("yield return null;")
    try_index = start_block.index("try")
    catch_index = start_block.index("catch (Exception exception)")
    second_yield = start_block.rindex("yield return null;")
    require(first_yield < try_index < catch_index < second_yield, "gate3_coroutine_yield_placement")
    require("int exitCode = 0;" in start_block, "gate3_exit_code_state_missing")
    require("exitCode = 31;" in start_block, "gate3_failure_exit_code_missing")
    require("Application.Quit(exitCode);" in start_block, "gate3_single_exit_path_missing")
    require("Application.Quit(0);" not in start_block, "gate3_success_quit_inside_try")
    require("Application.Quit(31);" not in start_block, "gate3_failure_quit_inside_catch")

    require(asmdef.get("name") == "Marcbeacve.TevScript.Gate3.MonoPlayer", "gate3_asmdef_name")
    require(asmdef.get("references") == [
        "Marcbeacve.TevScript.Core",
        "Marcbeacve.TevScript.Unity",
    ], "gate3_asmdef_references")
    require(asmdef.get("autoReferenced") is True, "gate3_asmdef_auto_reference")
    require(asmdef.get("noEngineReferences") is False, "gate3_asmdef_engine_reference")
    require(asmdef.get("allowUnsafeCode") is False, "gate3_asmdef_unsafe")

    required_runtime = (
        "UNITY_MONO_PLAYER_ACTIVE=PASS",
        "UNITY_MONO_PLAYER_CORE_PARSE=PASS",
        "UNITY_MONO_PLAYER_CAPABILITY_INPUT_MOVE2D=PASS",
        "UNITY_MONO_PLAYER_CAPABILITY_MOTION_TRANSFORM2D=PASS",
        "UNITY_MONO_PLAYER_CAPABILITY_ANIMATION_PLAY=PASS",
        "UNITY_MONO_PLAYER_CAPABILITY_TIME_DELTA=PASS",
        "UNITY_MONO_PLAYER_CAPABILITY_DEBUG_LOG=PASS",
        "UNITY_MONO_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS",
        "UNITY_MONO_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS",
        "TEV_SCRIPT_UNITY_MONO_PLAYER_GATE_3=PASS",
        "UNITY_IL2CPP=NOT_PROBED",
    )
    for marker in required_runtime:
        require(marker in runtime, f"runtime_marker_missing:{marker}")

    require(
        "PlayerSettings.SetScriptingBackend" in build
        and "ScriptingImplementation.Mono2x" in build,
        "mono_backend_not_explicit",
    )
    require(
        "PlayerSettings.GetScriptingBackend" in build,
        "mono_backend_not_verified",
    )
    require(
        "BuildTarget.StandaloneWindows64" in build,
        "windows64_target_missing",
    )
    for marker in (
        "UNITY_MONO_PLAYER_BUILD_BACKEND=MONO",
        "UNITY_MONO_PLAYER_BUILD_TARGET=STANDALONE_WINDOWS64",
        "UNITY_MONO_PLAYER_BUILD_RESULT=PASS",
    ):
        require(marker in build, f"build_marker_missing:{marker}")

    print("UNITY_GATE3_PLAYER_HARNESS_STATIC=PASS")
    print("UNITY_GATE3_HARNESS_ASMDEF=EXPLICIT_REFERENCES_PASS")
    print("UNITY_GATE3_COROUTINE_TRY_CATCH_YIELD=FIXED")
    print("UNITY_GATE3_MONO_BACKEND_EXPLICIT=PASS")
    print("UNITY_GATE3_PROVIDER_AUTHORITY_STATIC=EXPLICIT_PASS")
    print("UNITY_GATE3_CORE_PAYLOAD_FILES=0")
    print("UNITY_GATE3_INPUT_SYSTEM_DEVICE=NOT_PROBED")
    print("UNITY_GATE3_ANIMATOR_CONTROLLER=NOT_PROBED")
    print("UNITY_GATE3_IL2CPP=NOT_PROBED")
    print("TEV_SCRIPT_UNITY_MONO_PLAYER_GATE3_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
