from __future__ import annotations

from typing import Any

from .canonical import canonical_hash, canonical_json
from .file_observation_acquisition_v2 import MAX_FILE_READ_BYTES_V2
from .program_ir_v4 import (
    PROGRAM_IR_V4_EFFECTS_SCHEMA,
    PROGRAM_IR_V4_PURE_SCHEMA,
    PROGRAM_IR_V4_RECURSIVE_SCHEMA,
)
from .program_ir_v4_effect_commands import PROGRAM_IR_V4_EFFECTS_R2_SCHEMA
from .source_program_v2 import LANGUAGE_VERSION_V2
from . import release_metadata_v2 as release_metadata


V2_CERTIFIED_BASE_SHA = "284ec3ec8c41681825ec1a8421f7ee2a1b012d68"
V2_NORMATIVE_PATHS = (
    "spec/TEV_SCRIPT_V2_LANGUAGE.md",
    "spec/TEV_SCRIPT_PROGRAM_IR_V4.md",
    "spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md",
    "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
)
V2_SCHEMA_PATHS = (
    "schemas/tev-script-v2-descriptor.schema.json",
    "schemas/tev-script-program-ir-v4.schema.json",
    "schemas/tev-script-v2-filesystem-artifacts.schema.json",
    "schemas/tev-script-v2-certify-full-receipt.schema.json",
)
V2_COMMANDS = (
    "descriptor",
    "check",
    "compile",
    "verify-signed-remote-module-manifest",
    "acquire-signed-remote-modules",
    "extract-signed-remote-module-bundle",
    "check-remote-module-manifest",
    "acquire-remote-modules",
    "extract-remote-module-bundle",
    "bundle-modules",
    "check-modules",
    "compile-modules",
    "check-effects",
    "scenario-effects",
    "compile-effects",
    "request-file-observations",
    "acquire-file-observations",
    "check-effects-r2",
    "scenario-effects-r2",
    "compile-effects-r2",
    "plan-effects-r2",
    "authorize-file-effects-r2",
    "commit-file-effects-r2",
    "run",
)


def v2_descriptor() -> dict[str, Any]:
    release_metadata.validate_release_metadata()
    body: dict[str, Any] = {
        "schema": "TEV_SCRIPT_V2_DESCRIPTOR_V1",
        "language_version": LANGUAGE_VERSION_V2,
        "release_profile": release_metadata.RELEASE_PROFILE,
        "release_status": release_metadata.RELEASE_STATUS,
        "stable": release_metadata.STABLE,
        "source_extension": ".tevs",
        "program_ir_schemas": [
            PROGRAM_IR_V4_PURE_SCHEMA,
            PROGRAM_IR_V4_RECURSIVE_SCHEMA,
            PROGRAM_IR_V4_EFFECTS_SCHEMA,
            PROGRAM_IR_V4_EFFECTS_R2_SCHEMA,
        ],
        "commands": list(V2_COMMANDS),
        "runtime_requires_source_compiler": False,
        "boundaries": {
            "dynamic_code": False,
            "unbounded_loops": False,
            "uncontracted_recursion": False,
            "implicit_host_io": False,
            "runtime_source_compilation": False,
            "physical_effect_commit": "explicit_grant_only",
            "file_provider_batch": "single_file_replace_v1",
        },
        "filesystem_safety": {
            "authority_anchor": "OPEN_DIRECTORY_OBJECT_IDENTITY_V1",
            "path_resolution": "HANDLE_RELATIVE_NO_FOLLOW_V1",
            "maximum_file_read_bytes": MAX_FILE_READ_BYTES_V2,
            "oversize_witness_bytes": 1,
            "replace_linearization": "SAME_DIRECTORY_ATOMIC_RENAME_V1",
            "unsupported_platform_fails_closed": True,
        },
        "authority": {
            "normative_specifications": list(V2_NORMATIVE_PATHS),
            "json_schemas": list(V2_SCHEMA_PATHS),
            "feature_matrix": "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
            "canonical_index": "CANONICAL_INDEX.json",
        },
        "certification": {
            "certify_full_gate": "RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py",
            "receipt_schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1",
            "historical_receipt_schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1",
            "current_receipt_schema": "TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2",
            "python_certify_full_gate": "RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py",
            "stable_admission_gate": "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
            "certified_base_sha": V2_CERTIFIED_BASE_SHA,
            "technical_parent_commit": release_metadata.TECHNICAL_PARENT_COMMIT,
            "technical_parent_certificate_sha256": release_metadata.TECHNICAL_PARENT_CERTIFICATE_SHA256,
            "exact_git_identity_required": True,
            "clean_worktree_required": True,
            "v1_certificate_is_v2_authority": False,
            "current_v2_certify_full_claim": release_metadata.CURRENT_V2_CERTIFY_FULL_CLAIM,
            "current_v2_language_stable_claim": release_metadata.CURRENT_V2_LANGUAGE_STABLE_CLAIM,
            "publication_authorized": False,
            "merge_authorized": False,
        },
        "stable_release_surface": {
            "release_metadata": "tev_script/release_metadata_v2.py",
            "governance": "tools/validate_v2_stable_governance.py",
            "admission_gate": "RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py",
            "receipt_schema": "TEV_SCRIPT_V2_STABLE_ADMISSION_RECEIPT_V1",
            "exact_parent_certificate_required": True,
            "release_diff_whitelist_required": True,
            "artifact_byte_identity_required": True,
            "stable_claim": release_metadata.STABLE,
        },
        "public_interfaces": {
            "module_cli": "python -m tev_script.cli_v2",
            "installed_cli": "tev-script-v2",
            "descriptor_module_cli": "python -m tev_script.describe_v2",
            "descriptor_installed_cli": "tev-script-v2-describe",
        },
    }
    return {**body, "descriptor_hash": canonical_hash(body)}


def v2_descriptor_json() -> str:
    return canonical_json(v2_descriptor())
