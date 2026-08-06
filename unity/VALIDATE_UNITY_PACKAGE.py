from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
UNITY = ROOT / "unity"
PACKAGE = UNITY / "Package"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)




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

def verify_identity(filename: str, schema: str) -> int:
    payload = load_json(UNITY / filename)
    require(payload.get("schema") == schema, f"identity_schema:{filename}")
    files = payload.get("files")
    require(isinstance(files, list) and files, f"identity_files:{filename}")
    for item in files:
        canonical = ROOT / item["canonical"]
        package = ROOT / item["package"]
        require(canonical.is_file(), f"canonical_missing:{canonical}")
        require(package.is_file(), f"package_missing:{package}")
        observed = sha256(canonical)
        require(observed == item["sha256"], f"canonical_hash_drift:{canonical}")
        require(package.read_bytes() == canonical.read_bytes(), f"package_byte_drift:{package}")
    return len(files)


def main() -> int:
    package_json = load_json(PACKAGE / "package.json")
    require(package_json.get("name") == "com.marcbeacve.tev-script", "package_name")
    require(package_json.get("version") == "0.2.0-preview.1", "package_version")
    require(package_json.get("unity") == "6000.3", "unity_version_floor")

    core_asm = load_json(PACKAGE / "Runtime/Core/Marcbeacve.TevScript.Core.asmdef")
    require(core_asm.get("name") == "Marcbeacve.TevScript.Core", "core_asm_name")
    require(core_asm.get("references") == [], "core_asm_references")
    require(core_asm.get("noEngineReferences") is True, "core_must_not_reference_unity")
    require(core_asm.get("allowUnsafeCode") is False, "core_unsafe")

    editor_asm = load_json(PACKAGE / "Editor/Marcbeacve.TevScript.EditorGate.asmdef")
    require(editor_asm.get("references") == ["Marcbeacve.TevScript.Core"], "editor_gate_references")
    require(editor_asm.get("includePlatforms") == ["Editor"], "editor_gate_platform")

    core_count = verify_identity(
        "CORE_SOURCE_IDENTITY.json",
        "TEV_SCRIPT_UNITY_CORE_SOURCE_IDENTITY_V1",
    )
    fixture_count = verify_identity(
        "FIXTURE_IDENTITY.json",
        "TEV_SCRIPT_UNITY_FIXTURE_IDENTITY_V1",
    )
    require(core_count == 9, f"core_source_count:{core_count}")
    require(fixture_count == 12, f"fixture_count:{fixture_count}")

    combined = "\n".join(
        p.read_text(encoding="utf-8")
        for p in sorted((PACKAGE / "Runtime/Core").glob("*.cs"))
    )
    require("UnityEngine" not in combined, "unity_engine_leaked_into_core")
    require("UnityEditor" not in combined, "unity_editor_leaked_into_core")
    require("System.Reflection.Emit" not in combined, "dynamic_emit_in_core")

    gate_path = PACKAGE / "Editor/TevScriptUnityEditorGate.cs"
    gate = gate_path.read_text(encoding="utf-8")
    require(csharp_brace_balance(gate) == 0, "editor_gate_brace_mismatch")
    for source in sorted((PACKAGE / "Runtime/Core").glob("*.cs")):
        require(csharp_brace_balance(source.read_text(encoding="utf-8")) == 0,
                f"core_brace_mismatch:{source.name}")
    required_markers = (
        "TEV_SCRIPT_UNITY_EDITOR_GATE_1=PASS",
        "UNITY_THREE_RUNTIME_REFERENCE_PARITY=PASS",
        "UNITY_HOST_SEMANTIC_DRIFT=NONE_OBSERVED",
        "UNITY_MONO_PLAYER=NOT_PROBED",
        "UNITY_IL2CPP=NOT_PROBED",
    )
    for marker in required_markers:
        require(marker in gate, f"gate_marker_missing:{marker}")

    print("UNITY_PACKAGE_METADATA=PASS")
    print(f"UNITY_PACKAGE_CORE_SOURCE_IDENTITY={core_count}_PASS")
    print(f"UNITY_PACKAGE_FIXTURE_IDENTITY={fixture_count}_PASS")
    print("UNITY_PACKAGE_CORE_NO_ENGINE_REFERENCES=PASS")
    print("UNITY_PACKAGE_GATE_BOUNDARY=EDITOR_ONLY")
    print("TEV_SCRIPT_UNITY_PACKAGE_STATIC_GATE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
