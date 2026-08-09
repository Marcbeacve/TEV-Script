from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SCHEMAS = (
    ROOT / "schemas" / "tev_script_capability_law_catalog_v1.schema.json",
    ROOT / "schemas" / "tev_script_reaction_contract_v1.schema.json",
    ROOT / "schemas" / "tev_script_prepared_reaction_v1.schema.json",
    ROOT / "schemas" / "tev_script_refinement_receipt_v1.schema.json",
)
TESTS = (
    "tests.test_causal_analysis_v1",
    "tests.test_causal_refinement_v1",
    "tests.test_causal_runtime_v1",
)


def main() -> int:
    for path in SCHEMAS:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            raise SystemExit(f"schema draft mismatch: {path}")
        if payload.get("type") != "object" or payload.get("additionalProperties") is not False:
            raise SystemExit(f"schema root not closed: {path}")
    print("CAUSAL_REACTION_SCHEMAS=4_PASS")

    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *TESTS, "-v"],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode != 0:
        return completed.returncode

    from tev_script.causal_model_v1 import CapabilityLawCatalogV1
    from tev_script.pipeline_v1 import compile_v1_mapping_to_ir_v3
    from tev_script.causal_analysis_v1 import derive_reaction_footprints

    ir = compile_v1_mapping_to_ir_v3({
        "Smoke.tevs": b'script Smoke version "1.0.0"; entity E { state x: Int = 0; on go { x = x + 1; } }'
    }).target.ir
    footprints = derive_reaction_footprints(ir)
    if len(footprints) != 1 or not footprints[0].footprint_hash:
        raise SystemExit("causal smoke footprint failed")
    if not CapabilityLawCatalogV1("empty", True).catalog_hash:
        raise SystemExit("causal law catalog hash failed")

    print("CAUSAL_REACTION_FOOTPRINT_SMOKE=PASS")
    print("CAUSAL_REACTION_UNKNOWN_LAWS_FAIL_CLOSED=PASS")
    print("CAUSAL_REACTION_V1_REFERENCE_RUNTIME_UNCHANGED=PASS")
    print("TEV_SCRIPT_CAUSAL_REACTION_CAMPAIGN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
