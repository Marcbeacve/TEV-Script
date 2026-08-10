from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "tests.test_semantic_calculus_v0",
    "tests.test_semantic_advanced_v0",
    "tests.test_semantic_heterogeneous_v0",
    "tests.test_semantic_ir_projection_v0",
    "tests.test_semantic_governance_v0",
)

def main() -> int:
    schemas = (
        ROOT / "schemas" / "tev_script_semantic_field_v0.schema.json",
        ROOT / "schemas" / "tev_script_semantic_effect_atom_v0.schema.json",
        ROOT / "schemas" / "tev_script_semantic_calculus_manifest_v0.schema.json",
    )
    for path in schemas:
        obj = json.loads(path.read_text(encoding="utf-8"))
        if obj.get("additionalProperties") is not False:
            return 2
    manifest = json.loads((ROOT / "spec" / "TEV_SCRIPT_SEMANTIC_CALCULUS_V0.json").read_text(encoding="utf-8"))
    if manifest.get("schema") != "TEV_SCRIPT_SEMANTIC_CALCULUS_MANIFEST_V0":
        return 3
    p = subprocess.run([sys.executable, "-m", "unittest", *MODULES], cwd=ROOT)
    if p.returncode:
        return p.returncode
    causal = ROOT / "tests" / "run_causal_reaction_campaign.py"
    if causal.exists():
        c = subprocess.run([sys.executable, str(causal)], cwd=ROOT, capture_output=True, text=True)
        if c.returncode:
            sys.stdout.write(c.stdout)
            sys.stderr.write(c.stderr)
            return c.returncode
        print("CAUSAL_COMPATIBILITY_IF_PRESENT=PASS")
    print("TEV_SCRIPT_SEMANTIC_CALCULUS_V0=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
