from __future__ import annotations

import subprocess
import sys

COMMANDS = (
    [sys.executable, "-m", "unittest", "tests.test_semantic_authority_decoupling_v0", "-v"],
    [sys.executable, "tools/validate_semantic_authority_decoupling_v0.py"],
)

def main() -> int:
    for command in COMMANDS:
        result = subprocess.run(command)
        if result.returncode != 0:
            return result.returncode
    print("TEV_SCRIPT_SEMANTIC_AUTHORITY_DECOUPLING_V0=PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
