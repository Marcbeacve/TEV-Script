from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script import ScriptRuntime, TevScriptError, compile_bytes
from tev_script.canonical import canonical_hash
from tev_script.capability_catalog import parse_capability_catalog
from tev_script.ir_validation import validate_program_ir
from tev_script.json_io import load_strict_json
from tev_script.types import CAPABILITIES


def semantic_part(program: dict) -> dict:
    return {
        key: value
        for key, value in program.items()
        if key not in {"semantic_hash", "debug", "debug_hash"}
    }


def selected_handler(program: dict, entity_id: str, event_id: str) -> dict:
    entity = next(item for item in program["entities"] if item["entity_id"] == entity_id)
    return next(item for item in entity["handlers"] if item["event_id"] == event_id)


def main() -> int:
    corpus = load_strict_json(ROOT / "conformance" / "language-negative-v1.json")
    base = load_strict_json(ROOT / corpus["base_program"])
    validate_program_ir(base)
    print("LANGUAGE_CLOSURE_PYTHON_VALID_BASE=PASS")

    observed: list[str] = []
    for case in corpus["cases"]:
        mutated = copy.deepcopy(base)
        handler = selected_handler(mutated, corpus["entity_id"], corpus["handler_event_id"])
        handler["locals"] = copy.deepcopy(case["locals"])
        handler["instructions"] = copy.deepcopy(case["instructions"])
        handler["instruction_budget"] = max(1, len(handler["instructions"]))
        mutated["semantic_hash"] = canonical_hash(semantic_part(mutated))
        try:
            validate_program_ir(mutated)
        except TevScriptError as error:
            if error.diagnostic.code != corpus["expected_code"]:
                raise AssertionError(
                    f"{case['id']}: expected {corpus['expected_code']}, got {error.diagnostic.code}"
                ) from error
            observed.append(case["id"])
            continue
        raise AssertionError(f"negative case accepted: {case['id']}")
    if len(observed) != 8:
        raise AssertionError(f"expected 8 negative cases, got {len(observed)}")
    print("LANGUAGE_CLOSURE_PYTHON_NEGATIVE_CORPUS=8_PASS")

    unicode_source = '''script Ω version "0.2.0";\nentity E { on start { return; } }\n'''.encode("utf-8")
    try:
        compile_bytes("unicode-id.tevs", unicode_source)
    except TevScriptError as error:
        if error.diagnostic.code != "TEVS_LEX_IDENTIFIER_NON_ASCII":
            raise
    else:
        raise AssertionError("non-ASCII source identifier was accepted")
    print("LANGUAGE_CLOSURE_SOURCE_ASCII_IDENTIFIERS=PASS")

    portable_raw = load_strict_json(ROOT / "catalogs" / "portable_capabilities_v1.json")
    portable_loaded = parse_capability_catalog(portable_raw)
    if portable_loaded != CAPABILITIES:
        raise AssertionError("portable capability catalog does not match compiler mirror")
    print("LANGUAGE_CLOSURE_PORTABLE_CATALOG_PARITY=PASS")

    custom_catalog = parse_capability_catalog(
        {
            "schema": "TEV_SCRIPT_CAPABILITY_CATALOG_V1",
            "capabilities": [
                {
                    "capability_id": "sensor.temperature",
                    "parameters": [],
                    "return_type": "Rat",
                    "kind": "observation",
                }
            ],
        }
    )
    custom_source = b'''script Custom version "0.2.0";
entity E {
    state temperature: Rat = 0;
    on start {
        let observed: Rat = sensor.temperature();
        temperature = observed;
    }
}
'''
    bundle = compile_bytes(
        "custom-capability.tevs",
        custom_source,
        capability_catalog=custom_catalog,
    )
    validate_program_ir(bundle.ir)
    capabilities = bundle.ir["entities"][0]["capabilities"]
    if [item["capability_id"] for item in capabilities] != ["sensor.temperature"]:
        raise AssertionError("custom capability was not lowered into IR")
    print("LANGUAGE_CLOSURE_CUSTOM_CAPABILITY_CATALOG=PASS")

    try:
        ScriptRuntime(base).invoke("Player", " start ")
    except TevScriptError as error:
        if error.diagnostic.code != "TEVS_RUNTIME_INVOCATION_ID":
            raise
    else:
        raise AssertionError("non-canonical invocation id was accepted")
    print("LANGUAGE_CLOSURE_PYTHON_ABI_CANONICAL_ID=PASS")

    try:
        ScriptRuntime(base, {" debug.log": lambda value: None})
    except TevScriptError as error:
        if error.diagnostic.code != "TEVS_RUNTIME_CAPABILITY_BINDING_ID":
            raise
    else:
        raise AssertionError("non-canonical capability binding id was accepted")
    print("LANGUAGE_CLOSURE_PYTHON_CAPABILITY_BINDING_ID=PASS")
    print("TEV_SCRIPT_LANGUAGE_CLOSURE_PYTHON=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
