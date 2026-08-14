from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from tev_script import descriptor_v2
from tev_script import release_metadata_v2 as release_metadata

ROOT = Path(__file__).resolve().parents[1]
STABLE_TOOLING_PATHS = (
    "tev_script/release_metadata_v2.py",
    "tools/v2_certification_support.py",
    "schemas/tev-script-v2-certify-full-receipt-v2.schema.json",
    "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py",
    "schemas/tev-script-v2-python-certify-full-receipt.schema.json",
    "tools/validate_v2_stable_governance.py",
    "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
    "schemas/tev-script-v2-stable-admission-receipt.schema.json",
    "tools/validate_v2_stable_tooling_authority.py",
)
SCHEMA_PATHS = (
    "schemas/tev-script-v2-certify-full-receipt-v2.schema.json",
    "schemas/tev-script-v2-python-certify-full-receipt.schema.json",
    "schemas/tev-script-v2-stable-admission-receipt.schema.json",
)
EXPECTED_GATES = {
    "authority": "tools/validate_v2_authority.py",
    "filesystem_safety": "tools/validate_v2_filesystem_safety.py",
    "certify_full": "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py",
    "python_certify_full": "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py",
    "stable_governance": "tools/validate_v2_stable_governance.py",
    "stable_admission": "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
    "v1_non_regression": "RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py",
}


class V2StableToolingAuthorityFailure(RuntimeError):
    pass


def _require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise V2StableToolingAuthorityFailure(code + ":" + detail)


def _load(root: Path, relative: str) -> dict[str, Any]:
    path = root / relative
    _require(path.is_file(), "V2_STABLE_TOOLING_FILE_MISSING", relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2StableToolingAuthorityFailure(
            f"V2_STABLE_TOOLING_JSON:{relative}:{error}"
        ) from error
    _require(
        isinstance(value, dict),
        "V2_STABLE_TOOLING_JSON_ROOT",
        relative,
    )
    return value


def _v2_target(index: dict[str, Any]) -> dict[str, Any]:
    targets = [
        item
        for item in index.get("candidate_language_targets", [])
        if isinstance(item, dict) and item.get("language_version") == "2.0.0"
    ]
    _require(
        len(targets) == 1,
        "V2_STABLE_TOOLING_TARGET_COUNT",
        str(len(targets)),
    )
    return targets[0]


def _expected_surface(stable: bool) -> dict[str, object]:
    return {
        "release_metadata": "tev_script/release_metadata_v2.py",
        "governance": "tools/validate_v2_stable_governance.py",
        "admission_gate": "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
        "receipt_schema": "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1",
        "exact_parent_certificate_required": True,
        "release_diff_whitelist_required": True,
        "artifact_byte_identity_required": True,
        "stable_claim": stable,
    }


def validate_stable_tooling_authority(
    profile: str = "candidate",
    *,
    root: Path = ROOT,
) -> None:
    _require(
        profile in {"candidate", "stable"},
        "V2_STABLE_TOOLING_PROFILE",
        repr(profile),
    )
    try:
        release_metadata.validate_release_metadata()
    except RuntimeError as error:
        raise V2StableToolingAuthorityFailure(
            "V2_STABLE_TOOLING_RELEASE_METADATA:" + str(error)
        ) from error
    _require(
        release_metadata.RELEASE_PROFILE == profile,
        "V2_STABLE_TOOLING_RELEASE_PROFILE",
        repr(release_metadata.RELEASE_PROFILE),
    )
    stable = release_metadata.STABLE
    _require(
        stable is (profile == "stable"),
        "V2_STABLE_TOOLING_STABLE",
        repr(stable),
    )

    for relative in STABLE_TOOLING_PATHS:
        _require(
            (root / relative).is_file(),
            "V2_STABLE_TOOLING_PATH_MISSING",
            relative,
        )
    for relative in SCHEMA_PATHS:
        schema = _load(root, relative)
        Draft202012Validator.check_schema(schema)

    matrix = _load(root, "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    index = _load(root, "CANONICAL_INDEX.json")
    target = _v2_target(index)
    for label, owner in (("matrix", matrix), ("target", target)):
        observed = tuple(owner.get("stable_tooling_authority", ()))
        _require(
            observed == STABLE_TOOLING_PATHS,
            "V2_STABLE_TOOLING_INVENTORY_" + label.upper(),
            repr(observed),
        )

    gates = target.get("gates")
    _require(
        isinstance(gates, dict),
        "V2_STABLE_TOOLING_GATES",
        "missing",
    )
    for name, expected in EXPECTED_GATES.items():
        _require(
            gates.get(name) == expected,
            "V2_STABLE_TOOLING_GATE_BINDING",
            f"{name}:{gates.get(name)!r}",
        )

    expected_surface = _expected_surface(stable)
    target_surface = target.get("stable_release_surface")
    _require(
        target_surface == expected_surface,
        "V2_STABLE_TOOLING_TARGET_SURFACE",
        repr(target_surface),
    )
    descriptor_surface = descriptor_v2.v2_descriptor().get(
        "stable_release_surface"
    )
    _require(
        descriptor_surface == expected_surface,
        "V2_STABLE_TOOLING_DESCRIPTOR_SURFACE",
        repr(descriptor_surface),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate TEV Script V2 stable tooling authority"
    )
    parser.add_argument(
        "--profile",
        choices=("candidate", "stable"),
        default="candidate",
    )
    args = parser.parse_args(argv)
    try:
        validate_stable_tooling_authority(args.profile)
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY=FAIL")
        print(
            "TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY_ERROR="
            + type(error).__name__
            + ":"
            + str(error)
        )
        return 1
    print(
        "TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY_PROFILE="
        + args.profile
    )
    print("TEV_SCRIPT_V2_STABLE_TOOLING_SCHEMAS=PASS")
    print("TEV_SCRIPT_V2_STABLE_TOOLING_AUTHORITY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
