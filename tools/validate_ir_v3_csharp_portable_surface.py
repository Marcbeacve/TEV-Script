from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSHARP = ROOT / "runtimes" / "csharp"
CORE = CSHARP / "TevScript.Core"
V3_PROJECT = CSHARP / "TevScript.Core.V3" / "TevScript.Core.V3.csproj"

V3_SOURCES = (
    "TevScriptV3Lexical.cs",
    "TevScriptV3Values.cs",
    "TevScriptV3Canonical.cs",
    "TevScriptV3ObjectTreeJson.cs",
    "TevScriptV3StrictJson.cs",
    "TevScriptV3Flow.cs",
    "TevScriptV3Validation.cs",
    "TevScriptRuntimeV3.cs",
    "TevScriptRuntimeCheckpointV2.cs",
    "TevScriptRuntimeHotSwapV3.cs",
    "TevScriptUpdateV3.cs",
    "TevScriptV3Conformance.cs",
)

RUNTIME_CONSUMERS = (
    CSHARP / "TevScript.V3ConformanceGate" / "TevScript.V3ConformanceGate.csproj",
    CSHARP / "TevScript.V3CheckpointGate" / "TevScript.V3CheckpointGate.csproj",
    CSHARP / "TevScript.V3BrowserWasmGate" / "TevScript.V3BrowserWasmGate.csproj",
    CSHARP / "TevScript.V3WasiGate" / "TevScript.V3WasiGate.csproj",
)

SIGNED_UPDATE_CONSUMERS = (
    CSHARP / "TevScript.V3SignedUpdateGate" / "TevScript.V3SignedUpdateGate.csproj",
    CSHARP / "TevScript.V3BrowserSignedUpdateGate" / "TevScript.V3BrowserSignedUpdateGate.csproj",
    CSHARP / "TevScript.V3WasiSignedUpdateGate" / "TevScript.V3WasiSignedUpdateGate.csproj",
)


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise RuntimeError(f"{label}_MISSING:{needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise RuntimeError(f"{label}_FORBIDDEN:{needle}")


def require_v3_consumer(project: Path) -> str:
    if not project.is_file():
        raise RuntimeError(f"IR_V3_CSHARP_CONSUMER_MISSING:{project}")
    text = project.read_text(encoding="utf-8")
    require(text, "TevScript.Core.V3", "IR_V3_CSHARP_CONSUMER_BINDING")
    forbid(text, "../TevScript.Core/TevScript.Core.csproj", "IR_V3_CSHARP_CONSUMER_BINDING")
    forbid(text, "..\\TevScript.Core\\TevScript.Core.csproj", "IR_V3_CSHARP_CONSUMER_BINDING")
    return text


def main() -> int:
    core_project = (CORE / "TevScript.Core.csproj").read_text(encoding="utf-8")
    require(
        core_project,
        "<TargetFramework>netstandard2.1</TargetFramework>",
        "IR_V3_CSHARP_CORE_TFM",
    )
    require(core_project, '<Compile Remove="*V3*.cs" />', "IR_V3_CSHARP_V0_2_ISOLATION")
    require(
        core_project,
        '<Compile Remove="TevScriptRuntimeCheckpointV2.cs" />',
        "IR_V3_CSHARP_V0_2_ISOLATION",
    )
    for forbidden in (
        "PackageReference",
        "TevScript.Core.V3",
        "<TargetFramework>net8.0</TargetFramework>",
        "<TargetFramework>net9.0</TargetFramework>",
        "<TargetFramework>net10.0</TargetFramework>",
    ):
        forbid(core_project, forbidden, "IR_V3_CSHARP_V0_2_CORE")

    v3_project = V3_PROJECT.read_text(encoding="utf-8")
    require(v3_project, "<TargetFramework>net8.0</TargetFramework>", "IR_V3_CSHARP_V3_TFM")
    require(v3_project, "<EnableDefaultCompileItems>false</EnableDefaultCompileItems>", "IR_V3_CSHARP_V3_SOURCE_SET")
    forbid(v3_project, "PackageReference", "IR_V3_CSHARP_V3_DEPENDENCY")
    forbid(v3_project, "TevScript.Core.csproj", "IR_V3_CSHARP_V3_DEPENDENCY")
    forbid(v3_project, "CompilerCompatibility.V3.cs", "IR_V3_CSHARP_V3_SOURCE_SET")
    for name in ("GlobalUsings.V3.cs", *V3_SOURCES):
        require(v3_project, f"../TevScript.Core/{name}", "IR_V3_CSHARP_V3_SOURCE_SET")

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
        '.GetField("_ir"',
        "SHA256.HashData",
        "SHA256.Create",
        "Convert.ToHexString",
        "ArgumentNullException.ThrowIfNull",
        "Marcbeacve.TevScript.Core.TevJson",
        "System.Text.Json.JsonSerializer",
        "System.Text.RegularExpressions",
        "RegexOptions.",
        "Regex.",
    ):
        forbid(joined, forbidden, "IR_V3_CSHARP_V3_RUNTIME_SURFACE")

    canonical = sources["TevScriptV3Canonical.cs"]
    for witness in (
        "Sha256RoundConstants",
        "ComputeSha256",
        "RotateRight",
        "WriteUInt32BigEndian",
    ):
        require(canonical, witness, "IR_V3_CSHARP_PORTABLE_SHA256")

    object_tree = sources["TevScriptV3ObjectTreeJson.cs"]
    for witness in (
        "TevScriptObjectTreeJsonV3",
        "IDictionary<string, object?>",
        "case IDictionary dictionary",
        "case IEnumerable sequence",
        "internal static class JsonSerializer",
        "TevScriptObjectTreeJsonV3.Element(value)",
    ):
        require(object_tree, witness, "IR_V3_CSHARP_AOT_JSON")

    conformance = sources["TevScriptV3Conformance.cs"]
    require(conformance, "runtimeProgram.IrForCheckpoint", "IR_V3_CSHARP_NO_REFLECTION")
    require(conformance, "JsonSerializer.SerializeToElement(value)", "IR_V3_CSHARP_AOT_JSON_BINDING")

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

    hot_swap = sources["TevScriptRuntimeHotSwapV3.cs"]
    for witness in (
        "TevScriptCapabilityContractV3",
        "SameSignature",
        "CaptureSnapshot",
        "RestoreCompatibleSnapshot",
        "TevScriptRuntimeSwapPlanV3",
        "SourceGeneration",
        "SourceSemanticHash",
        "TEVS_IR_V3_SWAP_PLAN_STALE",
        "RollbackLastCommit",
        "TEVS_IR_V3_SWAP_CAPABILITY_SIGNATURE_CEILING",
    ):
        require(hot_swap, witness, "IR_V3_CSHARP_TRANSACTIONAL_SWAP")

    update = sources["TevScriptUpdateV3.cs"]
    for witness in (
        'PackageSchema = "TEV_SCRIPT_SIGNED_UPDATE_PACKAGE_V2"',
        'BodySchema = "TEV_SCRIPT_UPDATE_BODY_V2"',
        "from_ir_semantic_hash",
        "target_ir_semantic_hash",
        "target_source_semantic_hash",
        "VerifySignature",
        "TEVS_UPDATE_V3_FROM_HASH",
        "ValidateReplay",
        "TEVS_UPDATE_V3_REPLAY",
        "TEVS_UPDATE_V3_EPOCH_ROLLBACK",
        "TEVS_UPDATE_V3_EPOCH_JUMP",
        "TEVS_UPDATE_V3_STORE_COMMIT",
        "RollbackLastCommit",
        "TryLoadInstalledPackage",
    ):
        require(update, witness, "IR_V3_CSHARP_SIGNED_UPDATE")
    forbid(update, "TryRestoreInstalled", "IR_V3_CSHARP_SIGNED_UPDATE_RESTART_BOUNDARY")

    for consumer in RUNTIME_CONSUMERS:
        text = require_v3_consumer(consumer)
        forbid(text, "TevScript.Update", "IR_V3_CSHARP_RUNTIME_CRYPTO_COUPLING")

    for consumer in SIGNED_UPDATE_CONSUMERS:
        text = require_v3_consumer(consumer)
        require(text, "TevScript.Update", "IR_V3_CSHARP_SIGNED_UPDATE_VERIFIER_BINDING")

    print("TEV_SCRIPT_IR_V3_CSHARP_CORE_TFM=NETSTANDARD2_1_PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_V0_2_ASSEMBLY_ISOLATION=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_V3_ASSEMBLY=NET8_DEPENDENCY_FREE_PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_REFLECTION_FREE=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_AOT_JSON=REFLECTION_FREE_PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SHA256=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_MODERN_API_GUARD=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_CHECKPOINT_BOUNDARY=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_TRANSACTIONAL_SWAP=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_SIGNED_UPDATE_CONSUMERS=3_PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_RUNTIME_CRYPTO_DECOUPLED=PASS")
    print("TEV_SCRIPT_IR_V3_CSHARP_PORTABLE_SURFACE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
