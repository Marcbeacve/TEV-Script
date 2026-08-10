from __future__ import annotations

from collections import Counter
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = (
    "test_causal_*.py",
    "test_semantic_*.py",
    "test_cuofc_correspondence_v0.py",
    "test_cuofc_residual_correspondence_v0.py",
)


def main() -> int:
    suite = unittest.TestSuite()
    for pattern in PATTERNS:
        suite.addTests(
            unittest.defaultTestLoader.discover(
                str(ROOT / "tests"),
                pattern=pattern,
                top_level_dir=str(ROOT),
            )
        )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    reasons = Counter(reason for _test, reason in result.skipped)
    print(f"POST_V1_INTEGRATION_TESTS_RUN={result.testsRun}")
    print(f"POST_V1_INTEGRATION_SKIP_COUNT={len(result.skipped)}")
    if reasons:
        print("POST_V1_INTEGRATION_SKIP_REASONS=" + repr(dict(sorted(reasons.items()))))
    if result.errors or result.failures or result.skipped:
        print("POST_V1_INTEGRATION_CAMPAIGN=FAIL")
        return 1
    print("POST_V1_CAUSAL_REACTION=PASS")
    print("POST_V1_SEMANTIC_CALCULUS=PASS")
    print("POST_V1_SEMANTIC_FRONTIER=PASS")
    print("POST_V1_AUTHORITY_DECOUPLING=PASS")
    print("POST_V1_CUOFC_CORRESPONDENCE=PASS")
    print("POST_V1_RESIDUAL=PASS")
    print("POST_V1_CAUSAL_SEMANTIC_BRIDGE=PASS")
    print("POST_V1_INTEGRATION_CAMPAIGN=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
