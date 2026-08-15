from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from jsonschema import Draft202012Validator  # noqa: E402
from tev_script.canonical import canonical_hash  # noqa: E402
import tev_script.descriptor_v2 as descriptor_v2  # noqa: E402
from tev_script import release_metadata_v2 as release_metadata  # noqa: E402
from tools import v2_certification_support as support  # noqa: E402

STABLE_STATUS = "STABLE_ADMISSION_REQUESTED"
STABLE_ADMISSION_GATE = "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py"
STABLE_RECEIPT_SCHEMA = "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1"
REQUIRED_STABLE_PROMOTION_GATES = {
    "STABLE_ADMISSION_TOOLING_TECHNICALLY_CERTIFIED_PASS",
    "STABLE_PARENT_CERTIFICATE_BINDING_PASS",
    "STABLE_RELEASE_DIFF_CONFINEMENT_PASS",
    "STABLE_V2_TECHNICAL_RECERTIFICATION_PASS",
    "STABLE_V1_NON_REGRESSION_PASS",
    "STABLE_V2_PYTHON_ARTIFACT_PASS",
    "EXACT_V2_STABLE_ADMISSION_PASS",
}


class V2StableGovernanceFailure(RuntimeError):
    pass


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise V2StableGovernanceFailure(code + ":" + detail)


def require_sha256(value: object, code: str) -> str:
    require(isinstance(value, str), code, repr(value))
    text = str(value)
    require(
        len(text) == 64
        and all(char in "0123456789abcdef" for char in text),
        code,
        text,
    )
    return text


def require_stable_release_metadata() -> tuple[str, str]:
    try:
        release_metadata.validate_release_metadata()
    except RuntimeError as error:
        raise V2StableGovernanceFailure(
            "V2_STABLE_GOVERNANCE_METADATA:" + str(error)
        ) from error
    require(
        release_metadata.RELEASE_PROFILE == "stable",
        "V2_STABLE_GOVERNANCE_PROFILE",
        release_metadata.RELEASE_PROFILE,
    )
    require(
        release_metadata.RELEASE_STATUS == "STABLE_2_0_0",
        "V2_STABLE_GOVERNANCE_STATUS",
        release_metadata.RELEASE_STATUS,
    )
    require(
        release_metadata.STABLE is True,
        "V2_STABLE_GOVERNANCE_STABLE",
        repr(release_metadata.STABLE),
    )
    require(
        release_metadata.CURRENT_V2_CERTIFY_FULL_CLAIM is True,
        "V2_STABLE_GOVERNANCE_CERTIFY_CLAIM",
        repr(release_metadata.CURRENT_V2_CERTIFY_FULL_CLAIM),
    )
    require(
        release_metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM is True,
        "V2_STABLE_GOVERNANCE_LANGUAGE_CLAIM",
        repr(release_metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM),
    )
    try:
        parent = support.require_git_sha(
            release_metadata.TECHNICAL_PARENT_COMMIT,
            "technical parent",
        )
    except support.V2CertificationFailure as error:
        raise V2StableGovernanceFailure(
            "V2_STABLE_GOVERNANCE_PARENT:" + str(error)
        ) from error
    certificate = require_sha256(
        release_metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256,
        "V2_STABLE_GOVERNANCE_PARENT_CERTIFICATE",
    )
    return parent, certificate


def _load_json(relative: str) -> dict[str, object]:
    path = ROOT / relative
    require(path.is_file(), "V2_STABLE_GOVERNANCE_FILE_MISSING", relative)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise V2StableGovernanceFailure(
            f"V2_STABLE_GOVERNANCE_JSON:{relative}:{error}"
        ) from error
    require(
        isinstance(value, dict),
        "V2_STABLE_GOVERNANCE_JSON_ROOT",
        relative,
    )
    return value


def _stable_target(index: dict[str, object]) -> dict[str, object]:
    raw = index.get("candidate_language_targets", [])
    targets = [
        item
        for item in raw
        if isinstance(item, dict) and item.get("language_version") == "2.0.0"
    ]
    require(
        len(targets) == 1,
        "V2_STABLE_GOVERNANCE_TARGET_COUNT",
        str(len(targets)),
    )
    return targets[0]


def _require_v2_release_documents(parent: str, certificate: str) -> None:
    required = (
        "V2_STABLE_ADMISSION=REQUESTED",
        "V2_LANGUAGE_VERSION=2.0.0",
        "V2_PYTHON_PACKAGE_VERSION=1.0.0",
        "V2_TECHNICAL_PARENT_COMMIT=" + parent,
        "V2_TECHNICAL_PARENT_CERTIFICATE_SHA256=" + certificate,
    )
    for relative in ("README.md", "CHANGELOG.md", "PROJECT_STATE.md"):
        text = (ROOT / relative).read_text(encoding="utf-8")
        for token in required:
            require(
                token in text,
                "V2_STABLE_GOVERNANCE_RELEASE_DOCUMENT",
                relative + ":" + token,
            )


def validate_stable_governance() -> None:
    parent, certificate = require_stable_release_metadata()

    index = _load_json("CANONICAL_INDEX.json")
    require(
        index.get("schema") == "TEV_SCRIPT_CANONICAL_INDEX_V1",
        "V2_STABLE_GOVERNANCE_INDEX_SCHEMA",
        repr(index.get("schema")),
    )
    target = _stable_target(index)
    require(
        target.get("status") == STABLE_STATUS,
        "V2_STABLE_GOVERNANCE_TARGET_STATUS",
        repr(target.get("status")),
    )
    require(
        target.get("stable") is True,
        "V2_STABLE_GOVERNANCE_TARGET_STABLE",
        repr(target.get("stable")),
    )
    require(
        target.get("publication_authorized") is False,
        "V2_STABLE_GOVERNANCE_PUBLICATION",
        repr(target.get("publication_authorized")),
    )
    require(
        target.get("merge_authorized") is False,
        "V2_STABLE_GOVERNANCE_MERGE",
        repr(target.get("merge_authorized")),
    )
    gates = target.get("gates")
    require(isinstance(gates, dict), "V2_STABLE_GOVERNANCE_GATES", "missing")
    require(
        gates.get("stable_admission") == STABLE_ADMISSION_GATE,
        "V2_STABLE_GOVERNANCE_STABLE_GATE",
        repr(gates.get("stable_admission")),
    )
    stable_surface = target.get("stable_release_surface")
    require(
        isinstance(stable_surface, dict),
        "V2_STABLE_GOVERNANCE_STABLE_SURFACE",
        "missing",
    )
    expected_surface = {
        "release_metadata": "tev_script/release_metadata_v2.py",
        "governance": "tools/validate_v2_stable_governance.py",
        "admission_gate": STABLE_ADMISSION_GATE,
        "receipt_schema": STABLE_RECEIPT_SCHEMA,
        "exact_parent_certificate_required": True,
        "release_diff_whitelist_required": True,
        "artifact_byte_identity_required": True,
        "stable_claim": True,
    }
    for key, expected in expected_surface.items():
        require(
            stable_surface.get(key) == expected,
            "V2_STABLE_GOVERNANCE_STABLE_SURFACE",
            f"{key}:{stable_surface.get(key)!r}",
        )

    matrix = _load_json("spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json")
    require(
        matrix.get("schema") == "TEV_SCRIPT_V2_FEATURE_MATRIX_V1",
        "V2_STABLE_GOVERNANCE_MATRIX_SCHEMA",
        repr(matrix.get("schema")),
    )
    require(
        matrix.get("language_version") == "2.0.0",
        "V2_STABLE_GOVERNANCE_MATRIX_VERSION",
        repr(matrix.get("language_version")),
    )
    require(
        matrix.get("certification_status") == STABLE_STATUS,
        "V2_STABLE_GOVERNANCE_MATRIX_STATUS",
        repr(matrix.get("certification_status")),
    )
    require(
        matrix.get("stable") is True,
        "V2_STABLE_GOVERNANCE_MATRIX_STABLE",
        repr(matrix.get("stable")),
    )
    require(
        matrix.get("publication_authorized") is False,
        "V2_STABLE_GOVERNANCE_MATRIX_PUBLICATION",
        repr(matrix.get("publication_authorized")),
    )
    require(
        matrix.get("merge_authorized") is False,
        "V2_STABLE_GOVERNANCE_MATRIX_MERGE",
        repr(matrix.get("merge_authorized")),
    )
    promotion = {str(item) for item in matrix.get("promotion_gates", [])}
    missing = sorted(REQUIRED_STABLE_PROMOTION_GATES - promotion)
    require(
        not missing,
        "V2_STABLE_GOVERNANCE_PROMOTION_GATES",
        ",".join(missing),
    )

    descriptor = descriptor_v2.v2_descriptor()
    schema = _load_json("schemas/tev-script-v2-descriptor.schema.json")
    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(descriptor)
    body = dict(descriptor)
    observed_hash = body.pop("descriptor_hash")
    require(
        observed_hash == canonical_hash(body),
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_HASH",
        str(observed_hash),
    )
    require(
        descriptor.get("release_profile") == "stable",
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_PROFILE",
        repr(descriptor.get("release_profile")),
    )
    require(
        descriptor.get("release_status") == "STABLE_2_0_0",
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_STATUS",
        repr(descriptor.get("release_status")),
    )
    require(
        descriptor.get("stable") is True,
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_STABLE",
        repr(descriptor.get("stable")),
    )
    certification = descriptor.get("certification")
    require(
        isinstance(certification, dict),
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_CERT",
        "missing",
    )
    require(
        certification.get("technical_parent_commit") == parent,
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_PARENT",
        repr(certification.get("technical_parent_commit")),
    )
    require(
        certification.get("technical_parent_certificate_sha256") == certificate,
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_PARENT_CERT",
        repr(certification.get("technical_parent_certificate_sha256")),
    )
    require(
        certification.get("current_v2_certify_full_claim") is True,
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_CERTIFY_CLAIM",
        repr(certification.get("current_v2_certify_full_claim")),
    )
    require(
        certification.get("current_v2_language_stable_claim") is True,
        "V2_STABLE_GOVERNANCE_DESCRIPTOR_LANGUAGE_CLAIM",
        repr(certification.get("current_v2_language_stable_claim")),
    )

    project = tomllib.loads(
        (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]
    require(
        str(project.get("version")) == "1.0.0",
        "V2_STABLE_GOVERNANCE_PYTHON_VERSION",
        repr(project.get("version")),
    )
    require(
        project.get("dependencies", []) == [],
        "V2_STABLE_GOVERNANCE_PYTHON_DEPENDENCIES",
        repr(project.get("dependencies")),
    )
    scripts = project.get("scripts", {})
    require(
        isinstance(scripts, dict),
        "V2_STABLE_GOVERNANCE_PYTHON_SCRIPTS",
        "missing",
    )
    require(
        scripts.get("tev-script-v2") == "tev_script.cli_v2:main",
        "V2_STABLE_GOVERNANCE_V2_CLI",
        repr(scripts.get("tev-script-v2")),
    )
    require(
        scripts.get("tev-script-v2-describe")
        == "tev_script.describe_v2:main",
        "V2_STABLE_GOVERNANCE_V2_DESCRIPTOR_CLI",
        repr(scripts.get("tev-script-v2-describe")),
    )

    _require_v2_release_documents(parent, certificate)


def main() -> int:
    try:
        validate_stable_governance()
    except Exception as error:  # noqa: BLE001
        print("TEV_SCRIPT_V2_STABLE_GOVERNANCE=FAIL")
        print(
            "TEV_SCRIPT_V2_STABLE_GOVERNANCE_ERROR="
            + type(error).__name__
            + ":"
            + str(error)
        )
        return 1
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_RELEASE_METADATA=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_CANONICAL_INDEX=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_FEATURE_MATRIX=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_DESCRIPTOR=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_PYTHON_1_0_0=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE_RELEASE_DOCUMENTS=PASS")
    print("TEV_SCRIPT_V2_STABLE_GOVERNANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
