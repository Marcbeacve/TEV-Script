from __future__ import annotations

from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent.parent

CS = ROOT / "runtimes" / "csharp" / "TevScript.Core"
UNITY = ROOT / "unity" / "Package" / "Runtime" / "Core"
HOT = CS / "TevScriptRuntimeHotSwap.cs"
UNITY_HOT = UNITY / "TevScriptRuntimeHotSwap.cs"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    runtime = (CS / "TevScriptRuntime.cs").read_text(encoding="utf-8")
    unity_runtime = (
        UNITY / "TevScriptRuntime.cs"
    ).read_text(encoding="utf-8")
    require(
        "public sealed partial class TevScriptRuntime" in runtime,
        "csharp_runtime_not_partial",
    )
    require(
        "public sealed partial class TevScriptRuntime" in unity_runtime,
        "unity_runtime_not_partial",
    )

    require(HOT.is_file(), "hotswap_core_missing")
    require(UNITY_HOT.is_file(), "hotswap_unity_mirror_missing")
    require(
        HOT.read_bytes() == UNITY_HOT.read_bytes(),
        "hotswap_mirror_mismatch",
    )

    cs_names = sorted(path.name for path in CS.glob("*.cs"))
    unity_names = sorted(path.name for path in UNITY.glob("*.cs"))
    require(cs_names == unity_names, "core_source_name_set_mismatch")
    for name in cs_names:
        require(
            (CS / name).read_bytes() == (UNITY / name).read_bytes(),
            f"core_mirror_byte_mismatch:{name}",
        )

    text = HOT.read_text(encoding="utf-8")
    required = (
        "TevScriptRuntimeSnapshot",
        "TevScriptRuntimeSwapPlan",
        "TevScriptRuntimeSwapReceipt",
        "TevScriptRuntimeHost",
        "PrepareSwap",
        "Commit",
        "RollbackLastCommit",
        "TEVS_CS_SWAP_CAPABILITY_CEILING",
        "TEVS_CS_SWAP_PLAN_STALE",
        "TEVS_CS_SWAP_STATE_REMOVED",
        "TEVS_CS_SWAP_STATE_TYPE",
        "TEVS_CS_SWAP_PROGRAM_ID",
        "lock (_sync)",
    )
    for marker in required:
        require(marker in text, f"hotswap_marker_missing:{marker}")

    forbidden = (
        "System.Reflection",
        "Assembly.Load",
        "Activator.CreateInstance",
        "DllImport",
        "HttpClient",
        "UnityWebRequest",
        "WebRequest",
        "System.Net",
        "dynamic ",
        "CSharpCodeProvider",
        "Roslyn",
    )
    for marker in forbidden:
        require(marker not in text, f"hotswap_forbidden:{marker}")

    gate = (
        ROOT /
        "runtimes/csharp/TevScript.TransactionalSwapGate/Program.cs"
    ).read_text(encoding="utf-8")
    for marker in (
        "GATE5A_GATE_BINARY_VERSION=V4",
        "GATE5A_PREPARE_NON_AUTHORITATIVE=PASS",
        "GATE5A_COMMIT_ATOMIC_REFERENCE_SWAP=PASS",
        "GATE5A_EXISTING_STATE_MIGRATION=PASS",
        "GATE5A_ADDITIVE_STATE_INITIALIZATION=PASS",
        "GATE5A_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS",
        "GATE5A_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS",
        "GATE5A_CAPABILITY_CEILING_FAIL_CLOSED=PASS",
        "GATE5A_STALE_PLAN_FAIL_CLOSED=PASS",
        "TEV_SCRIPT_TRANSACTIONAL_PROGRAM_SWAP_GATE_5A=PASS",
    ):
        require(marker in gate, f"gate_marker_missing:{marker}")

    print(f"GATE5A_CORE_SOURCE_IDENTITY={len(cs_names)}_PASS")
    print("GATE5A_RUNTIME_IMMUTABLE_PROGRAM_MODEL=PRESERVED")
    print("GATE5A_TRANSACTION_SUPERVISOR=PASS_STATIC")
    print("GATE5A_CAPABILITY_CEILING=EXPLICIT_PASS_STATIC")
    print("GATE5A_DYNAMIC_CODE=ABSENT_PASS")
    print("GATE5A_NETWORK=ABSENT_PASS")
    print("GATE5A_SIGNATURE_AUTHORITY=NOT_IN_SCOPE")
    print("TEV_SCRIPT_TRANSACTIONAL_PROGRAM_SWAP_GATE5A_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
