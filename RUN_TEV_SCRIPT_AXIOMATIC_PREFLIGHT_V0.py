from __future__ import annotations

from pathlib import Path

from tools.validate_axiomatic_coverage_v0 import validate as validate_coverage
from tools.validate_axiomatic_evidence_contract_v0 import (
    validate as validate_evidence_contract,
)
from tools.validate_axiomatic_operational_v0 import validate as validate_operational
from tools.validate_axiomatic_semantics_v0 import validate as validate_semantics
from tools.validate_axiomatic_system_correspondence_v0 import (
    validate as validate_system_correspondence,
)

ROOT = Path(__file__).resolve().parent


def main() -> int:
    checks = (
        ("SEMANTICS", lambda: validate_semantics(ROOT)),
        ("SYSTEM_CORRESPONDENCE", validate_system_correspondence),
        ("OPERATIONAL", validate_operational),
        ("CLOSED_COVERAGE", validate_coverage),
        ("EVIDENCE_CONTRACT", validate_evidence_contract),
    )
    failures: list[str] = []
    for name, run in checks:
        current = tuple(run())
        if current:
            failures.extend(f"{name}:{item}" for item in current)
            print(f"TEV_SCRIPT_AXIOMATIC_PREFLIGHT_{name}=FAIL")
        else:
            print(f"TEV_SCRIPT_AXIOMATIC_PREFLIGHT_{name}=PASS")
    if failures:
        for failure in failures:
            print("TEV_SCRIPT_AXIOMATIC_PREFLIGHT_V0=FAIL:" + failure)
        return 1
    print("TEV_SCRIPT_AXIOMATIC_PREFLIGHT_V0=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
