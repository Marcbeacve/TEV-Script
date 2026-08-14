from __future__ import annotations

from io import StringIO
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


CASE_TO_TEST = {
    "RELATIVE_TRAVERSAL_REJECTED": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_rejects_ambiguous_or_escaping_relative_paths_before_access",
    "WINDOWS_AMBIGUOUS_SEGMENT_REJECTED": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_rejects_ambiguous_or_escaping_relative_paths_before_access",
    "PARENT_LINK_OR_JUNCTION_REJECTED": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_parent_link_or_junction_escape_is_rejected",
    "PARENT_SWAP_AFTER_ROOT_OPEN_REJECTED": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_parent_swap_to_junction_after_scope_open_fails_closed",
    "ROOT_PATH_REPLACEMENT_READS_PINNED_OBJECT": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_scope_pins_root_object_across_path_replacement_for_read",
    "ROOT_PATH_REPLACEMENT_WRITES_PINNED_OBJECT": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_scope_pins_root_object_across_path_replacement_for_replace",
    "OVERSIZE_READ_CONSUMES_AT_MOST_LIMIT_PLUS_ONE": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_bounded_consumer_never_requests_or_retains_more_than_limit_plus_one",
    "OVERSIZE_READ_NOT_DECODED_OR_HASHED": "tests.test_file_observation_acquisition_v2.FileObservationAcquisitionV2Tests.test_oversize_rejection_never_uses_unbounded_path_read",
    "ATOMIC_REPLACE_VERIFIES_OPEN_TEMP_HANDLE": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_scope_pins_root_object_across_path_replacement_for_replace",
    "UNSUPPORTED_SECURE_PRIMITIVE_FAILS_CLOSED": "tests.test_scoped_filesystem_v2.ScopedFilesystemV2Tests.test_unavailable_secure_backend_fails_closed_without_path_fallback"
}


class V2FilesystemSafetyFailure(RuntimeError):
    pass


def _test_ids(suite: unittest.TestSuite) -> set[str]:
    observed: set[str] = set()
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            observed.update(_test_ids(item))
        else:
            observed.add(item.id())
    return observed


def validate_v2_filesystem_safety() -> int:
    fixture_path = ROOT / "conformance" / "v2-filesystem-safety-cases.json"
    try:
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2FilesystemSafetyFailure(f"cannot load filesystem safety fixture: {error}") from error
    if fixture.get("schema") != "TEV_SCRIPT_V2_FILESYSTEM_SAFETY_CASES_V1":
        raise V2FilesystemSafetyFailure("filesystem safety fixture schema mismatch")
    if fixture.get("maximum_file_read_bytes") != 1048576 or fixture.get("overflow_witness_bytes") != 1:
        raise V2FilesystemSafetyFailure("filesystem safety budget mismatch")
    required = fixture.get("required_case_ids")
    if not isinstance(required, list) or set(required) != set(CASE_TO_TEST) or len(required) != len(set(required)):
        raise V2FilesystemSafetyFailure("filesystem safety required-case inventory mismatch")
    modules = fixture.get("mandatory_test_modules")
    if not isinstance(modules, list) or not modules:
        raise V2FilesystemSafetyFailure("filesystem safety mandatory modules are missing")
    suite = unittest.defaultTestLoader.loadTestsFromNames(modules)
    observed_ids = _test_ids(suite)
    missing_tests = sorted(set(CASE_TO_TEST.values()) - observed_ids)
    if missing_tests:
        raise V2FilesystemSafetyFailure(f"filesystem safety mapped tests are missing: {missing_tests}")
    stream = StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    if not result.wasSuccessful() or result.skipped:
        raise V2FilesystemSafetyFailure(
            "filesystem safety tests failed or skipped: "
            + stream.getvalue()[-12000:].replace("\n", "\\n")
        )
    return result.testsRun


def main() -> int:
    try:
        count = validate_v2_filesystem_safety()
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_V2_FILESYSTEM_SAFETY=FAIL")
        print("TEV_SCRIPT_V2_FILESYSTEM_SAFETY_ERROR=" + type(error).__name__ + ":" + str(error))
        return 1
    print(f"FILESYSTEM_SAFETY=PASS tests={count}")
    print("TOCTOU_CLOSURE=PASS")
    print("ONE_MIB_PRE_ADMISSION=PASS")
    print("TEV_SCRIPT_V2_FILESYSTEM_SAFETY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
