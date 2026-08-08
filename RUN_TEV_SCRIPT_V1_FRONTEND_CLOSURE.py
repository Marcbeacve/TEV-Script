from __future__ import annotations

import compileall
import hashlib
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
V1_JSON_INPUTS = (
    "conformance/v1-source-syntax-cases.json",
    "conformance/v1-linker-cases.json",
    "conformance/v1-static-semantics-cases.json",
    "conformance/v1-behavior-composition-cases.json",
    "conformance/v1-constant-cases.json",
    "conformance/v1-linked-program-cases.json",
    "conformance/v1-irv2-lowering-cases.json",
    "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
    "schemas/tev_script_linked_program_v1.schema.json",
    "schemas/tev_script_lowering_receipt_v1.schema.json",
    "CANONICAL_INDEX.json",
)
V0_2_TESTS = ("test_canonical.py", "test_compiler.py", "test_conformance.py")


def main() -> int:
    print("TEV_SCRIPT_V1_FRONTEND_CLOSURE_SCHEMA=V3")
    print("V0_2_CERTIFIED_BASE=6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5")

    compiled = compileall.compile_dir(str(ROOT / "tev_script"), quiet=1) and compileall.compile_dir(
        str(ROOT / "tests"), quiet=1
    )
    print("TEV_SCRIPT_V1_PYTHON_COMPILE=" + ("PASS" if compiled else "FAIL"))
    if not compiled:
        return 1

    manifest: list[dict[str, str]] = []
    try:
        for relative in V1_JSON_INPUTS:
            data = (ROOT / relative).read_bytes()
            json.loads(data.decode("utf-8"))
            manifest.append({"path": relative, "sha256": hashlib.sha256(data).hexdigest()})
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        print(f"TEV_SCRIPT_V1_JSON_INPUTS=FAIL error={type(exc).__name__}:{exc}")
        return 1
    manifest.sort(key=lambda item: item["path"])
    manifest_bytes = json.dumps(
        manifest,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    print(f"TEV_SCRIPT_V1_JSON_INPUTS=PASS count={len(manifest)}")
    print(f"TEV_SCRIPT_V1_JSON_MANIFEST_SHA256={hashlib.sha256(manifest_bytes).hexdigest()}")

    v1_suite = unittest.defaultTestLoader.discover(
        str(ROOT / "tests"), pattern="test_v1_*.py", top_level_dir=str(ROOT)
    )
    v1_result = unittest.TextTestRunner(verbosity=2).run(v1_suite)
    print(f"TEV_SCRIPT_V1_TESTS_RUN={v1_result.testsRun}")
    print("TEV_SCRIPT_V1_TESTS=" + ("PASS" if v1_result.wasSuccessful() else "FAIL"))
    if not v1_result.wasSuccessful():
        return 1

    v02_suite = unittest.TestSuite()
    for filename in V0_2_TESTS:
        v02_suite.addTests(
            unittest.defaultTestLoader.discover(
                str(ROOT / "tests"), pattern=filename, top_level_dir=str(ROOT)
            )
        )
    v02_result = unittest.TextTestRunner(verbosity=2).run(v02_suite)
    print(f"TEV_SCRIPT_V0_2_REGRESSION_TESTS_RUN={v02_result.testsRun}")
    print(
        "TEV_SCRIPT_V0_2_PYTHON_REGRESSION="
        + ("PASS" if v02_result.wasSuccessful() else "FAIL")
    )
    if not v02_result.wasSuccessful():
        return 1

    print("TEV_SCRIPT_V1_LINKED_PROGRAM=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_LINKED_PROGRAM_SCHEMA=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_IRV2_ERASABLE_LOWERING=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_LOWERING_RECEIPT=PASS_CANDIDATE")
    print("V1_RUNTIME_IR3=NOT_IMPLEMENTED")
    print("V1_CROSS_RUNTIME_PARITY=NOT_CLAIMED")
    print("V1_STABLE_RELEASE=NO")
    print("TEV_SCRIPT_V1_FRONTEND_STATIC_CLOSURE=PASS_CANDIDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
