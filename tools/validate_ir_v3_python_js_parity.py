from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.canonical import canonical_json  # noqa: E402
from tev_script.ir_v3_conformance import run_ir_v3_conformance  # noqa: E402
from tev_script.json_io import load_strict_json  # noqa: E402


def main() -> int:
    node = shutil.which("node")
    if node is None:
        print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=SKIPPED_NODE_UNAVAILABLE")
        return 0

    cases = load_strict_json(ROOT / "conformance" / "ir-v3-validator-cases.json")
    scenario = load_strict_json(ROOT / "conformance" / "ir-v3-portable.scenario.json")
    program = cases["valid_program"]
    python_bundle = run_ir_v3_conformance(program, scenario)

    with tempfile.TemporaryDirectory(prefix="tev_script_ir_v3_parity_") as temp:
        temp_root = Path(temp)
        program_path = temp_root / "program.irv3.json"
        scenario_path = temp_root / "scenario.json"
        program_path.write_text(canonical_json(program), encoding="utf-8", newline="")
        scenario_path.write_text(canonical_json(scenario), encoding="utf-8", newline="")

        completed = subprocess.run(
            [
                node,
                str(ROOT / "javascript" / "src" / "run-ir-v3-conformance.mjs"),
                str(program_path),
                str(scenario_path),
            ],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    if completed.returncode != 0:
        print("TEV_SCRIPT_IR_V3_NODE_RUNNER=FAIL")
        if completed.stdout:
            print("NODE_STDOUT=" + completed.stdout[-4000:].replace("\n", "\\n"))
        if completed.stderr:
            print("NODE_STDERR=" + completed.stderr[-4000:].replace("\n", "\\n"))
        return 1

    node_receipt = completed.stdout
    if node_receipt != python_bundle.canonical_json:
        print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=FAIL_BYTE_MISMATCH")
        try:
            node_object = json.loads(node_receipt)
            print("PYTHON_RECEIPT_HASH=" + python_bundle.receipt_hash)
            print("NODE_RECEIPT_HASH=" + str(node_object.get("receipt_hash", "MISSING")))
        except json.JSONDecodeError:
            print("NODE_RECEIPT_JSON=INVALID")
        return 1

    node_object = json.loads(node_receipt)
    if node_object.get("receipt_hash") != python_bundle.receipt_hash:
        print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=FAIL_HASH_MISMATCH")
        return 1

    print("TEV_SCRIPT_IR_V3_NODE_RUNNER=PASS")
    print("TEV_SCRIPT_IR_V3_PYTHON_JS_CANONICAL_BYTES=PASS")
    print("TEV_SCRIPT_IR_V3_PYTHON_JS_RECEIPT_HASH=" + python_bundle.receipt_hash)
    print("TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
