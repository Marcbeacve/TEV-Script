from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
r=subprocess.run([sys.executable,"-m","unittest","tests.test_semantic_residual_v0","-v"],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
print(r.stdout,end="")
if r.returncode:
    print("TEV_SCRIPT_SEMANTIC_RESIDUAL_V0=FAIL"); raise SystemExit(r.returncode)
for marker in (
    "RESIDUAL_FIELD_IS_SEMANTIC_FIELD",
    "RESIDUAL_CLOSED_NULL",
    "RESIDUAL_RELEVANCE_SCOPED",
    "RESIDUAL_DETERMINISM",
    "RESIDUAL_APPLICATION_ADAPTER",
    "RESIDUAL_PROOF_ADAPTER",
    "RESIDUAL_COUNTERMODEL_ADAPTER",
    "RESIDUAL_DIVERGENCE_ADAPTER",
    "RESIDUAL_LAYER_ADAPTERS_DECOUPLED",
    "RESIDUAL_CUOFC_RUNTIME_DEPENDENCY_ABSENT",
): print(marker+"=PASS")
print("TEV_SCRIPT_SEMANTIC_RESIDUAL_V0=PASS")
