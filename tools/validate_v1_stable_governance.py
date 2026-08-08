from __future__ import annotations

import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tev_script.descriptor_v1 import v1_descriptor  # noqa: E402
from tev_script.release_metadata_v1 import (  # noqa: E402
    CURRENT_V1_CERTIFY_FULL_CLAIM,
    CURRENT_V1_LANGUAGE_STABLE_CLAIM,
    RELEASE_PROFILE,
    RELEASE_STATUS,
    STABLE,
    STABLE_LANGUAGE_VERSION,
    TECHNICAL_PARENT_CERTIFICATE_SHA256,
    TECHNICAL_PARENT_COMMIT,
    validate_release_metadata,
)

STABLE_STATUS = "STABLE_ADMISSION_REQUESTED"
STABLE_ADMISSION_GATE = "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py"


def require(condition: bool, code: str, detail: str) -> None:
    if not condition:
        raise RuntimeError(code + ":" + detail)


def load_json(relative: str) -> dict[str, object]:
    path = ROOT / relative
    require(path.is_file(), "V1_STABLE_GOVERNANCE_FILE_MISSING", relative)
    value = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(value, dict), "V1_STABLE_GOVERNANCE_JSON_ROOT", relative)
    return value


def require_sha(value: object, length: int, code: str) -> str:
    require(isinstance(value, str), code, repr(value))
    require(len(value) == length, code, value)
    require(all(char in "0123456789abcdef" for char in value), code, value)
    return value


def main() -> int:
    validate_release_metadata()
    require(RELEASE_PROFILE == "stable", "V1_STABLE_GOVERNANCE_PROFILE", RELEASE_PROFILE)
    require(RELEASE_STATUS == "STABLE_1_0_0", "V1_STABLE_GOVERNANCE_RELEASE_STATUS", RELEASE_STATUS)
    require(STABLE is True, "V1_STABLE_GOVERNANCE_STABLE", repr(STABLE))
    require(CURRENT_V1_CERTIFY_FULL_CLAIM is True, "V1_STABLE_GOVERNANCE_CERTIFY_CLAIM", repr(CURRENT_V1_CERTIFY_FULL_CLAIM))
    require(CURRENT_V1_LANGUAGE_STABLE_CLAIM is True, "V1_STABLE_GOVERNANCE_LANGUAGE_CLAIM", repr(CURRENT_V1_LANGUAGE_STABLE_CLAIM))
    require_sha(TECHNICAL_PARENT_COMMIT, 40, "V1_STABLE_GOVERNANCE_PARENT_COMMIT")
    require_sha(
        TECHNICAL_PARENT_CERTIFICATE_SHA256,
        64,
        "V1_STABLE_GOVERNANCE_PARENT_CERTIFICATE",
    )

    canonical = load_json("CANONICAL_INDEX.json")
    require(
        canonical.get("schema") == "TEV_SCRIPT_CANONICAL_INDEX_V1",
        "V1_STABLE_GOVERNANCE_CANONICAL_SCHEMA",
        repr(canonical.get("schema")),
    )
    # Top-level V0.2 historical authority remains unchanged.
    require(canonical.get("language_version") == "0.2.0", "V1_STABLE_GOVERNANCE_V0_2_INDEX_VERSION", repr(canonical.get("language_version")))
    require(canonical.get("stable") is False, "V1_STABLE_GOVERNANCE_V0_2_INDEX_STABLE", repr(canonical.get("stable")))

    targets = [
        item
        for item in canonical.get("candidate_language_targets", [])
        if isinstance(item, dict) and item.get("language_version") == STABLE_LANGUAGE_VERSION
    ]
    require(len(targets) == 1, "V1_STABLE_GOVERNANCE_TARGET_COUNT", str(len(targets)))
    target = targets[0]
    require(target.get("status") == STABLE_STATUS, "V1_STABLE_GOVERNANCE_TARGET_STATUS", repr(target.get("status")))
    require(target.get("stable") is True, "V1_STABLE_GOVERNANCE_TARGET_STABLE", repr(target.get("stable")))

    introspection = target.get("introspection_surface")
    require(isinstance(introspection, dict), "V1_STABLE_GOVERNANCE_INTROSPECTION", "missing")
    require(introspection.get("stable_claim") is True, "V1_STABLE_GOVERNANCE_INTROSPECTION_STABLE", repr(introspection.get("stable_claim")))

    python_surface = target.get("python_production_surface")
    require(isinstance(python_surface, dict), "V1_STABLE_GOVERNANCE_PYTHON_SURFACE", "missing")
    require(python_surface.get("stable_claim") is True, "V1_STABLE_GOVERNANCE_PYTHON_STABLE", repr(python_surface.get("stable_claim")))
    require(python_surface.get("runtime_accepts_source") is False, "V1_STABLE_GOVERNANCE_RUNTIME_SOURCE", repr(python_surface.get("runtime_accepts_source")))
    require(python_surface.get("least_authority_default") is True, "V1_STABLE_GOVERNANCE_LEAST_AUTHORITY", repr(python_surface.get("least_authority_default")))
    require(python_surface.get("serialized_host_access") is True, "V1_STABLE_GOVERNANCE_SERIALIZED_HOST", repr(python_surface.get("serialized_host_access")))

    gates = target.get("gates")
    require(isinstance(gates, dict), "V1_STABLE_GOVERNANCE_GATES", "missing")
    require(gates.get("stable_admission") == STABLE_ADMISSION_GATE, "V1_STABLE_GOVERNANCE_STABLE_GATE", repr(gates.get("stable_admission")))
    require((ROOT / STABLE_ADMISSION_GATE).is_file(), "V1_STABLE_GOVERNANCE_STABLE_GATE_FILE", STABLE_ADMISSION_GATE)

    matrix = load_json("spec/TEV_SCRIPT_V1_FEATURE_MATRIX.json")
    require(matrix.get("schema") == "TEV_SCRIPT_V1_FEATURE_MATRIX_V5", "V1_STABLE_GOVERNANCE_MATRIX_SCHEMA", repr(matrix.get("schema")))
    require(matrix.get("target_language_version") == STABLE_LANGUAGE_VERSION, "V1_STABLE_GOVERNANCE_MATRIX_VERSION", repr(matrix.get("target_language_version")))
    require(matrix.get("repository_language_version_remains") == STABLE_LANGUAGE_VERSION, "V1_STABLE_GOVERNANCE_REPOSITORY_VERSION", repr(matrix.get("repository_language_version_remains")))
    require(matrix.get("stable_release_authorized") is True, "V1_STABLE_GOVERNANCE_MATRIX_STABLE", repr(matrix.get("stable_release_authorized")))
    require(matrix.get("certification_status") == STABLE_STATUS, "V1_STABLE_GOVERNANCE_MATRIX_STATUS", repr(matrix.get("certification_status")))

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    require(str(project.get("version")) == STABLE_LANGUAGE_VERSION, "V1_STABLE_GOVERNANCE_PYTHON_VERSION", repr(project.get("version")))
    require(project.get("dependencies", []) == [], "V1_STABLE_GOVERNANCE_PYTHON_DEPENDENCIES", repr(project.get("dependencies")))

    javascript = load_json("javascript/package.json")
    require(javascript.get("version") == STABLE_LANGUAGE_VERSION, "V1_STABLE_GOVERNANCE_JAVASCRIPT_VERSION", repr(javascript.get("version")))
    require(javascript.get("license") == "UNLICENSED", "V1_STABLE_GOVERNANCE_JAVASCRIPT_LICENSE", repr(javascript.get("license")))

    descriptor = v1_descriptor()
    require(descriptor.get("language_version") == STABLE_LANGUAGE_VERSION, "V1_STABLE_GOVERNANCE_DESCRIPTOR_VERSION", repr(descriptor.get("language_version")))
    require(descriptor.get("release_profile") == "stable", "V1_STABLE_GOVERNANCE_DESCRIPTOR_PROFILE", repr(descriptor.get("release_profile")))
    require(descriptor.get("release_status") == "STABLE_1_0_0", "V1_STABLE_GOVERNANCE_DESCRIPTOR_STATUS", repr(descriptor.get("release_status")))
    require(descriptor.get("stable") is True, "V1_STABLE_GOVERNANCE_DESCRIPTOR_STABLE", repr(descriptor.get("stable")))
    certification = descriptor.get("certification")
    require(isinstance(certification, dict), "V1_STABLE_GOVERNANCE_DESCRIPTOR_CERTIFICATION", "missing")
    require(certification.get("technical_parent_commit") == TECHNICAL_PARENT_COMMIT, "V1_STABLE_GOVERNANCE_DESCRIPTOR_PARENT", repr(certification.get("technical_parent_commit")))
    require(
        certification.get("technical_parent_certificate_sha256") == TECHNICAL_PARENT_CERTIFICATE_SHA256,
        "V1_STABLE_GOVERNANCE_DESCRIPTOR_PARENT_CERTIFICATE",
        repr(certification.get("technical_parent_certificate_sha256")),
    )
    require(certification.get("current_v1_certify_full_claim") is True, "V1_STABLE_GOVERNANCE_DESCRIPTOR_CERTIFY_CLAIM", repr(certification.get("current_v1_certify_full_claim")))
    require(certification.get("current_v1_language_stable_claim") is True, "V1_STABLE_GOVERNANCE_DESCRIPTOR_LANGUAGE_CLAIM", repr(certification.get("current_v1_language_stable_claim")))

    state = (ROOT / "PROJECT_STATE.md").read_text(encoding="utf-8")
    for token in (
        "STABLE_ADMISSION=REQUESTED",
        "LANGUAGE_STABLE_CLAIM=REQUESTED",
        "TECHNICAL_PARENT_COMMIT=" + TECHNICAL_PARENT_COMMIT,
        "TECHNICAL_PARENT_CERTIFICATE_SHA256=" + TECHNICAL_PARENT_CERTIFICATE_SHA256,
    ):
        require(token in state, "V1_STABLE_GOVERNANCE_PROJECT_STATE", token)

    protocol = (ROOT / "docs" / "V1_CERTIFICATION_PROTOCOL.md").read_text(encoding="utf-8")
    for token in (
        "RUN_TEV_SCRIPT_V1_STABLE_ADMISSION.py",
        "TEV_SCRIPT_V1_STABLE_ADMISSION_RECEIPT_V1",
        "STABLE_ADMISSION=PASS",
        "LANGUAGE_STABLE=YES",
    ):
        require(token in protocol, "V1_STABLE_GOVERNANCE_PROTOCOL", token)

    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE_RELEASE_METADATA=PASS")
    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE_CANONICAL_INDEX=PASS")
    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE_FEATURE_MATRIX=PASS")
    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE_DESCRIPTOR=PASS")
    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE_DISTRIBUTION_VERSIONS=PASS")
    print("TEV_SCRIPT_V1_STABLE_GOVERNANCE=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
