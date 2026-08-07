from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, marker: str) -> None:
    if not condition:
        raise SystemExit(f"LANGUAGE_COMPLETENESS_STATIC_FAIL={marker}")
    print(marker)


def text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def main() -> int:
    required = [
        "spec/SOURCE_LEXICAL_GRAMMAR_V1.md",
        "spec/STATIC_SEMANTICS_V1.md",
        "spec/IR_OPERATIONAL_SEMANTICS_V1.md",
        "schemas/tev_script_capability_catalog_v1.schema.json",
        "conformance/language-negative-v1.json",
        "tev_script/capability_catalog.py",
        "tev_script/ir_flow.py",
        "javascript/src/ir-flow.mjs",
        "runtimes/csharp/TevScript.Core/TevScriptIrFlowVerifier.cs",
        "unity/Package/Runtime/Core/TevScriptIrFlowVerifier.cs",
        "runtimes/csharp/TevScript.LanguageClosureGate/Program.cs",
        "RUN_TEV_SCRIPT_LANGUAGE_COMPLETENESS_V1.py",
    ]
    require(all((ROOT / path).is_file() for path in required), "LANGUAGE_COMPLETENESS_REQUIRED_SURFACE=PASS")

    ebnf = text("spec/TEV_SCRIPT_V0_2.ebnf")
    require("Pratt expression" not in ebnf and "or_expression" in ebnf and "ASCII_ALPHA" in ebnf,
            "LANGUAGE_COMPLETENESS_SOURCE_GRAMMAR=PASS")

    compiler = text("tev_script/compiler.py")
    require("validate_program_ir(result)" in compiler and "capability_catalog" in compiler,
            "LANGUAGE_COMPLETENESS_SOURCE_TO_IR_CLOSURE=PASS")

    lexer = text("tev_script/lexer.py")
    require("TEVS_LEX_IDENTIFIER_NON_ASCII" in lexer and "_is_ascii_identifier_start" in lexer,
            "LANGUAGE_COMPLETENESS_ASCII_IDENTIFIER_BOUNDARY=PASS")

    corpus = json.loads(text("conformance/language-negative-v1.json"))
    require(corpus.get("schema") == "TEV_SCRIPT_LANGUAGE_NEGATIVE_CORPUS_V1"
            and corpus.get("expected_code") == "TEVS_IR_FLOW_INVALID"
            and len(corpus.get("cases", [])) == 8,
            "LANGUAGE_COMPLETENESS_NEGATIVE_CORPUS=8_PASS")

    schema = json.loads(text("schemas/tev_script_capability_catalog_v1.schema.json"))
    require(schema.get("title") == "TEV Script Capability Catalog V1",
            "LANGUAGE_COMPLETENESS_CAPABILITY_CATALOG_SCHEMA=PASS")

    flow_sources = [
        text("tev_script/ir_flow.py"),
        text("javascript/src/ir-flow.mjs"),
        text("runtimes/csharp/TevScript.Core/TevScriptIrFlowVerifier.cs"),
    ]
    require(all("TEVS_IR_FLOW_INVALID" in source for source in flow_sources),
            "LANGUAGE_COMPLETENESS_FLOW_ERROR_PARITY=PASS")

    mirror_pairs = [
        "TevScriptIrFlowVerifier.cs",
        "TevScriptIrValidator.cs",
        "TevScriptRuntime.cs",
        "TevScriptContracts.cs",
    ]
    for name in mirror_pairs:
        left = (ROOT / "runtimes/csharp/TevScript.Core" / name).read_bytes()
        right = (ROOT / "unity/Package/Runtime/Core" / name).read_bytes()
        require(left == right, f"LANGUAGE_COMPLETENESS_CORE_MIRROR_{name}=PASS")

    identity = json.loads(text("unity/CORE_SOURCE_IDENTITY.json"))
    require(len(identity.get("files", [])) == 13,
            "LANGUAGE_COMPLETENESS_UNITY_CORE_IDENTITY=13_PASS")

    contracts = text("runtimes/csharp/TevScript.Core/TevScriptContracts.cs")
    runtime = text("runtimes/csharp/TevScript.Core/TevScriptRuntime.cs")
    require("CapabilityId = capabilityId.Trim()" not in contracts and "eventId.Trim()" not in runtime,
            "LANGUAGE_COMPLETENESS_NO_SILENT_ID_NORMALIZATION=PASS")
    require("TEVS_RUNTIME_INVOCATION_ID" in runtime and "TEVS_RUNTIME_CAPABILITY_BINDING_ID" in contracts,
            "LANGUAGE_COMPLETENESS_ABI_CANONICAL_IDS=PASS")

    package = json.loads(text("javascript/package.json"))
    require("./ir-flow" in package.get("exports", {}) and "src/ir-flow.mjs" in package.get("files", []),
            "LANGUAGE_COMPLETENESS_JS_PACKAGE_FLOW=PASS")

    runner = text("RUN_TEV_SCRIPT_LANGUAGE_COMPLETENESS_V1.py")
    forbidden = ["git push", "gh pr", "git merge", "git tag", "git reset --hard"]
    require(not any(item in runner.lower() for item in forbidden),
            "LANGUAGE_COMPLETENESS_REMOTE_WRITE_GUARD=PASS")

    require("language-negative-v1.json" in text("spec/CONFORMANCE_PROTOCOL_V1.md"),
            "LANGUAGE_COMPLETENESS_NEGATIVE_PROTOCOL_AUTHORITY=PASS")

    require("Async tasks/promises" in text("spec/RUNTIME_ABI_V1.md")
            and "Static flow verification" in text("spec/IR_OPERATIONAL_SEMANTICS_V1.md"),
            "LANGUAGE_COMPLETENESS_EXPLICIT_BOUNDARIES=PASS")

    print("TEV_SCRIPT_LANGUAGE_COMPLETENESS_STATIC=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
