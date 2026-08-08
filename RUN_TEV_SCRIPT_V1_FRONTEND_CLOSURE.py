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
    "conformance/ir-v3-validator-cases.json",
    "conformance/ir-v3-portable.scenario.json",
    "spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json",
    "schemas/tev_script_project_v1.schema.json",
    "schemas/tev_script_linked_program_v1.schema.json",
    "schemas/tev_script_lowering_receipt_v1.schema.json",
    "schemas/tev_script_lowering_receipt_v2.schema.json",
    "schemas/tev_script_program_ir_v3.schema.json",
    "schemas/tev_script_ir_v3_scenario_v1.schema.json",
    "schemas/tev_script_ir_v3_conformance_receipt_v1.schema.json",
    "schemas/tev_script_runtime_checkpoint_v2.schema.json",
    "schemas/tev_script_signed_update_package_v2.schema.json",
    "schemas/tev_script_installed_update_v2.schema.json",
    "examples/v1/ecosystem/tevscript.project.json",
    "CANONICAL_INDEX.json",
)
V0_2_TESTS = ("test_canonical.py", "test_compiler.py", "test_conformance.py")
IR_V3_TEST_PATTERNS = (
    "test_ir_v3_*.py",
    "test_ir_v2_to_v3_lift.py",
    "test_runtime_checkpoint_v2.py",
)


def main() -> int:
    print("TEV_SCRIPT_V1_FRONTEND_CLOSURE_SCHEMA=V7")
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

    ir_v3_suite = unittest.TestSuite()
    for pattern in IR_V3_TEST_PATTERNS:
        ir_v3_suite.addTests(
            unittest.defaultTestLoader.discover(
                str(ROOT / "tests"), pattern=pattern, top_level_dir=str(ROOT)
            )
        )
    ir_v3_result = unittest.TextTestRunner(verbosity=2).run(ir_v3_suite)
    print(f"TEV_SCRIPT_IR_V3_TESTS_RUN={ir_v3_result.testsRun}")
    print("TEV_SCRIPT_IR_V3_TESTS=" + ("PASS" if ir_v3_result.wasSuccessful() else "FAIL"))
    if not ir_v3_result.wasSuccessful():
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
    print("TEV_SCRIPT_V1_LOWERING_RECEIPT_V1=PASS_CANDIDATE")
    print("TEV_SCRIPT_IR_V3_TYPE_VALUE_MODEL=PASS_CANDIDATE")
    print("TEV_SCRIPT_IR_V3_TYPED_CFG=PASS_CANDIDATE")
    print("TEV_SCRIPT_IR_V3_PYTHON_RUNTIME=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_TO_IR_V3_LOWERING=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_LOWERING_RECEIPT_V2=PASS_CANDIDATE")
    print("TEV_SCRIPT_IR_V2_TO_V3_LIFT=PASS_CANDIDATE")
    print("TEV_SCRIPT_RUNTIME_CHECKPOINT_V2=PASS_CANDIDATE")
    print("TEV_SCRIPT_SIGNED_UPDATE_V2_AUTHORITY_INPUTS=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_PROJECT_MANIFEST=PASS_CANDIDATE")
    print("TEV_SCRIPT_V1_EXAMPLES_CLI_PUBLIC_API=PASS_CANDIDATE")
    print("V1_CROSS_RUNTIME_PARITY=NOT_CLAIMED")
    print("V1_STABLE_RELEASE=NO")
    print("TEV_SCRIPT_V1_PYTHON_CLOSURE=PASS_CANDIDATE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
