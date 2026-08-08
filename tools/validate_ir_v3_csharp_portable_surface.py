from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "runtimes" / "csharp" / "TevScript.Core"

V3_SOURCES = (
    "TevScriptV3Values.cs",
    "TevScriptV3Canonical.cs",
    "TevScriptV3StrictJson.cs",
    "TevScriptV3Flow.cs",
    "TevScriptV3Validation.cs",
    "TevScriptRuntimeV3.cs",
    "TevScriptRuntimeCheckpointV2.cs",
    "TevScriptV3Conformance.cs",
)


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}_MISSING:{needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise RuntimeError(f"{label}_FORBIDDEN:{needle}")


def main() -> int:
    project = (CORE / "TevScript.Core.csproj").read_text(encoding="utf-8")
    require(
        project,
        "<TargetFramework>netstandard2.1</TargetFramework>",
        "IR_V3_CSHARP_CORE_TFM",
    )
    forbid(project, "<TargetFramework>net8.0</TargetFramework>", "IR_V3_CSHARP_CORE_TFM")
    forbid(project, "<TargetFramework>net9.0</TargetFramework>", "IR_V3_CSHARP_CORE_TFM")
    forbid(project, "<TargetFramework>net10.0</TargetFramework>", "IR_V3_CSHARP_CORE_TFM")

    sources: dict[str, str] = {}
    for name in V3_SOURCES:
        path = CORE / name
        if not path.is_file():
            raise RuntimeError(f"IR_V3_CSHARP_SOURCE_MISSING:{name}")
        sources[name] = path.read_text(encoding="utf-8")

    joined = "\n".join(sources.values())
    for forbidden in (
        "System.Reflection",
        "BindingFlags.",
        ".GetField(\"_ir\"",
        "SHA256.HashData",
        "Convert.ToHexString",
        "ArgumentNullException.ThrowIfNull",
    ):
        forbid(joined, forbidden, "IR_V3_CSHARP_PORTABLE_SURFACE")

    compatibility = (CORE / "CompilerCompatibility.V3.cs").read_text(encoding="utf-8")
    for witness in (
        "#if NETSTANDARD2_1",
        "class IsExternalInit",
        "class RequiredMemberAttribute",
        "class CompilerFeatureRequiredAttribute",
        "class SetsRequiredMembersAttribute",
        "class UnreachableException",
        "Order<T>",
        "class RegexOptions",
        "NonBacktracking =",
        "System.Text.RegularExpressions.RegexOptions.None",
        "class JsonSerializer",
        "SerializeToElement<T>",
        "class HashCode",
    ):
        require(compatibility, witness, "IR_V3_CSHARP_COMPATIBILITY")

    canonical = sources["TevScriptV3Canonical.cs"]
    require(canonical, "SHA256.Create()", "IR_V3_CSHARP_SHA256")
    require(canonical, "sha.ComputeHash(bytes)", "IR_V3_CSHARP_SHA256")

    conformance = sources["TevScriptV3Conformance.cs"]
    require(conformance, "runtimeProgram.IrForCheckpoint", "IR_V3_CSHARP_NO_REFLECTION")
    runtime = sources["TevScriptRuntimeV3.cs"]
    require(runtime, "internal JsonElement IrForCheckpoint", "IR_V3_CSHARP_INFRASTRUCTURE_BOUNDARY")
    require(runtime, "internal void RestoreStateForCheckpoint", "IR_V3_CSHARP_INFRASTRUCTURE_BOUNDARY")

    checkpoint = sources["TevScriptRuntimeCheckpointV2.cs"]
    for witness in (
        'public const string Schema = "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2"',
        "public static TevScriptRuntimeCheckpointV2 Capture",
        "public static TevScriptRuntimeCheckpointV2 Parse",
        "public TevScriptRuntimeV3 RestoreExact",
        "TEVS_CHECKPOINT_V2_SEMANTIC_HASH",
        "TEVS_CHECKPOINT_V2_SOURCE_HASH",
        "TEVS_CHECKPOINT_V2_ENTITY_SET",
        "TEVS_CHECKPOINT_V2_STATE_SET",
        "TEVS_CHECKPOINT_V2_STATE_TYPE",
    ):
        require(checkpoint, witness, "IR_V3_CSHARP_CHECKPOINT")

    print("TEV_SCRIPT_IR_V3_CSHARP_CORE_TFM=NETSTANDARD2_1_PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_REFLECTION_FREE=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_MODERN_API_GUARD=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_CHECKPOINT_BOUNDARY=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
