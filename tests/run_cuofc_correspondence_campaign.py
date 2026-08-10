from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "tests.test_cuofc_correspondence_v0",
    "tests.test_cuofc_residual_correspondence_v0",
)

r = subprocess.run(
    [sys.executable, "-m", "unittest", *MODULES, "-v"],
    cwd=ROOT,
    text=True,
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
)
print(r.stdout, end="")
if r.returncode:
    print("TEV_SCRIPT_CUOFC_CORRESPONDENCE_V0=FAIL")
    raise SystemExit(r.returncode)
for marker in (
    "CUOFC_FIELD_CORRESPONDENCE",
    "CUOFC_CENTER_CORRESPONDENCE",
    "CUOFC_TRANSFORMATION_CORRESPONDENCE",
    "CUOFC_EVIDENCE_CORRESPONDENCE",
    "CUOFC_PROJECT_COMMIT_CORRESPONDENCE",
    "CUOFC_RESIDUAL_CORRESPONDENCE",
    "CUOFC_RESIDUAL_PROGRESS_PRESERVATION",
    "CUOFC_NEGATIVE_BOUNDARIES",
    "CORRESPONDENCE_NON_NORMATIVE",
    "ADD_ONLY_AUTHORITY_NONINTERFERENCE",
    "NO_CIRCULAR_AUTHORITY",
    "TEV_SCRIPT_CUOFC_CORRESPONDENCE_V0",
):
    print(marker + "=PASS")
