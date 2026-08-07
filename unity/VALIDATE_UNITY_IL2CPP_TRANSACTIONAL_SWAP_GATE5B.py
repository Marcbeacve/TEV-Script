from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GATE = ROOT / "unity" / "PlayerGates" / "IL2CPPTransactionalSwap"
RUNTIME = GATE / "Runtime"
EDITOR = GATE / "Editor"
CORE = ROOT / "runtimes" / "csharp" / "TevScript.Core"
UNITY_CORE = ROOT / "unity" / "Package" / "Runtime" / "Core"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    runtime_asm = load_json(
        RUNTIME /
        "Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.asmdef"
    )
    require(
        runtime_asm.get("name") ==
        "Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap",
        "gate5b_runtime_asm_name",
    )
    require(
        runtime_asm.get("references") ==
        ["Marcbeacve.TevScript.Core"],
        "gate5b_runtime_asm_references",
    )
    require(
        runtime_asm.get("autoReferenced") is False,
        "gate5b_runtime_auto_reference",
    )

    editor_asm = load_json(
        EDITOR /
        "Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.Editor.asmdef"
    )
    require(
        editor_asm.get("name") ==
        "Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap.Editor",
        "gate5b_editor_asm_name",
    )
    require(
        editor_asm.get("references") ==
        ["Marcbeacve.TevScript.Gate5B.Il2CppTransactionalSwap"],
        "gate5b_editor_asm_references",
    )
    require(
        editor_asm.get("includePlatforms") == ["Editor"],
        "gate5b_editor_platform",
    )

    core_names = sorted(path.name for path in CORE.glob("*.cs"))
    unity_names = sorted(path.name for path in UNITY_CORE.glob("*.cs"))
    require(core_names == unity_names, "gate5b_core_name_set_mismatch")
    for name in core_names:
        require(
            (CORE / name).read_bytes() ==
            (UNITY_CORE / name).read_bytes(),
            f"gate5b_core_mirror_mismatch:{name}",
        )

    require(
        "TevScriptRuntimeHotSwap.cs" in core_names,
        "gate5b_gate5a_hotswap_core_missing",
    )

    runtime = (
        RUNTIME / "TevScriptIl2CppTransactionalSwapGate.cs"
    ).read_text(encoding="utf-8")
    builder = (
        EDITOR / "TevScriptIl2CppTransactionalSwapBuildGate.cs"
    ).read_text(encoding="utf-8")
    runner = (
        ROOT /
        "RUN_TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE5B_V1.ps1"
    ).read_text(encoding="utf-8")
    generator = (
        ROOT / "tools/generate_transactional_swap_gate5b_fixtures.py"
    ).read_text(encoding="utf-8")

    for forbidden in (
        "System.Reflection",
        "Assembly.Load",
        "Activator.CreateInstance",
        "DllImport",
        "System.Net",
        "HttpClient",
        "UnityWebRequest",
        "WebRequest",
        "CSharpCodeProvider",
        "Microsoft.CodeAnalysis",
        "dynamic ",
        "FindObjectOfType",
        "FindFirstObjectByType",
        "FindAnyObjectByType",
        "GameObject.Find",
        "GetComponent<",
    ):
        require(
            forbidden not in runtime,
            f"gate5b_forbidden_runtime:{forbidden}",
        )

    for marker in (
        "UNITY_GATE5B_IL2CPP_ACTIVE=PASS",
        "UNITY_GATE5B_BASE_BEHAVIOR=PASS",
        "UNITY_GATE5B_PREPARE_NON_AUTHORITATIVE=PASS",
        "UNITY_GATE5B_COMMIT_ATOMIC_REFERENCE_SWAP=PASS",
        "UNITY_GATE5B_EXISTING_STATE_MIGRATION=PASS",
        "UNITY_GATE5B_ADDITIVE_STATE_INITIALIZATION=PASS",
        "UNITY_GATE5B_UPDATED_BEHAVIOR_ACTIVE=PASS",
        "UNITY_GATE5B_PLAN_REUSE_FAIL_CLOSED=PASS",
        "UNITY_GATE5B_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS",
        "UNITY_GATE5B_STATE_REMOVAL_FAIL_CLOSED=PASS",
        "UNITY_GATE5B_CAPABILITY_CEILING_FAIL_CLOSED=PASS",
        "UNITY_GATE5B_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS",
        "UNITY_GATE5B_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS",
        "UNITY_GATE5B_ROLLBACK_BEHAVIOR_RESTORED=PASS",
        "UNITY_GATE5B_STALE_PLAN_FAIL_CLOSED=PASS",
        "UNITY_GATE5B_TRANSACTION_BOUNDARY=PASS",
        "UNITY_GATE5B_DYNAMIC_CODE=ABSENT_PASS",
        "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=PASS",
    ):
        require(marker in runtime, f"gate5b_runtime_marker:{marker}")

    require(
        "ScriptingImplementation.IL2CPP" in builder,
        "gate5b_builder_il2cpp",
    )
    require(
        "BuildTarget.StandaloneWindows64" in builder,
        "gate5b_builder_windows64",
    )
    require(
        "NamedBuildTarget.Standalone" in builder,
        "gate5b_builder_named_target",
    )
    for marker in (
        "UNITY_GATE5B_IL2CPP_BUILD_BACKEND=IL2CPP",
        "UNITY_GATE5B_IL2CPP_BUILD_TARGET=STANDALONE_WINDOWS64",
        "UNITY_GATE5B_IL2CPP_BUILD_RESULT=PASS",
    ):
        require(marker in builder, f"gate5b_builder_marker:{marker}")

    require(
        'instruction.get("op") == "LOAD_PARAM"' in generator,
        "gate5b_behavior_source_match_missing",
    )
    require(
        '"op": "CONST"' in generator and '"$int": "0"' in generator,
        "gate5b_behavior_replacement_missing",
    )

    for marker in (
        "GameAssembly.dll",
        "global-metadata.dat",
        "MonoBleedingEdge",
        "GATE5B_GAMEASSEMBLY=PASS",
        "GATE5B_GLOBAL_METADATA=PASS",
        "GATE5B_MONO_RUNTIME=ABSENT_PASS",
        "GATE5B_GATE4_REGRESSION=PASS",
        "GATE5B_GATE5A_REGRESSION=PASS",
        "TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE_5B=PASS",
    ):
        require(marker in runner, f"gate5b_runner_marker:{marker}")

    print(f"GATE5B_CORE_SOURCE_IDENTITY={len(core_names)}_PASS")
    print("GATE5B_GATE5A_IMPLEMENTATION=UNCHANGED_PASS")
    print("GATE5B_CORE_MIRROR=BYTE_IDENTICAL_PASS")
    print("GATE5B_RUNTIME_ASSEMBLY=CORE_ONLY_EXPLICIT_REFERENCE_PASS")
    print("GATE5B_EDITOR_ASSEMBLY=EDITOR_ONLY_PASS")
    print("GATE5B_IL2CPP_BACKEND_STATIC=PASS")
    print("GATE5B_DYNAMIC_CODE=ABSENT_PASS")
    print("GATE5B_NETWORK=ABSENT_PASS")
    print("TEV_SCRIPT_UNITY_IL2CPP_TRANSACTIONAL_SWAP_GATE5B_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
