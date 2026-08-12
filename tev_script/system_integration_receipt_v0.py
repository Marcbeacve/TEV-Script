from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Mapping

from .canonical import canonical_hash, canonical_json

SYSTEM_INTEGRATION_RECEIPT_SCHEMA_V0 = "TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0"
_HEX = frozenset("0123456789abcdef")
_STABLE = re.compile(r"^[A-Za-z0-9_.:/+\-]+$")
_ROOT_FIELDS = frozenset(
    {
        "schema",
        "status",
        "source",
        "language_version",
        "system_api_contract_hash",
        "system_canonical_index",
        "system_integration_spec_sha256",
        "distribution",
        "verification",
        "receipt_hash",
    }
)
_SOURCE_FIELDS = frozenset({"branch", "head", "tree", "source_date_epoch"})
_INDEX_FIELDS = frozenset({"schema", "file_sha256"})
_DISTRIBUTION_FIELDS = frozenset(
    {
        "name",
        "version",
        "wheel",
        "wheel_sha256",
        "runtime_dependencies",
        "package_version_alone_is_identity",
    }
)
_VERIFICATION_FIELDS = frozenset(
    {
        "source_focal",
        "deterministic_wheel_bytes",
        "installed_wheel_import",
        "installed_api_identity",
        "installed_complete_causal_registry",
        "installed_complete_semantic_registry",
        "installed_receipt_verifier",
        "certify_full",
        "python_certify_full",
        "unity",
        "public_release",
    }
)


class SystemIntegrationReceiptError(ValueError):
    pass


def _mapping(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise SystemIntegrationReceiptError(what + " must be an object")
    result = dict(value)
    canonical_json(result)
    return result


def _fields(value: Mapping[str, object], expected: frozenset[str], what: str) -> None:
    observed = set(value)
    if observed != expected:
        missing = sorted(expected - observed)
        extra = sorted(observed - expected)
        raise SystemIntegrationReceiptError(f"{what} field set mismatch missing={missing} extra={extra}")


def _hash64(value: object, what: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(char not in _HEX for char in text):
        raise SystemIntegrationReceiptError(what)
    return text


def _git_hash40(value: object, what: str) -> str:
    text = str(value).lower()
    if len(text) != 40 or any(char not in _HEX for char in text):
        raise SystemIntegrationReceiptError(what)
    return text


def _stable(value: object, what: str) -> str:
    text = str(value)
    if not text or _STABLE.fullmatch(text) is None:
        raise SystemIntegrationReceiptError(what)
    return text


@dataclass(frozen=True, slots=True)
class SystemIntegrationReceiptV0:
    document: Mapping[str, object]

    def __post_init__(self) -> None:
        root = _mapping(self.document, "system integration receipt")
        _fields(root, _ROOT_FIELDS, "system integration receipt")
        if root["schema"] != SYSTEM_INTEGRATION_RECEIPT_SCHEMA_V0:
            raise SystemIntegrationReceiptError("system integration receipt schema mismatch")
        if root["status"] != "PASS":
            raise SystemIntegrationReceiptError("system integration receipt is not PASS")
        _stable(root["language_version"], "language_version")
        _hash64(root["system_api_contract_hash"], "system_api_contract_hash")
        _hash64(root["system_integration_spec_sha256"], "system_integration_spec_sha256")

        source = _mapping(root["source"], "source")
        _fields(source, _SOURCE_FIELDS, "source")
        _stable(source["branch"], "source branch")
        _git_hash40(source["head"], "source head")
        _git_hash40(source["tree"], "source tree")
        epoch = str(source["source_date_epoch"])
        if not epoch.isdigit():
            raise SystemIntegrationReceiptError("source_date_epoch")

        index = _mapping(root["system_canonical_index"], "system_canonical_index")
        _fields(index, _INDEX_FIELDS, "system_canonical_index")
        _stable(index["schema"], "system canonical index schema")
        _hash64(index["file_sha256"], "system canonical index file sha256")

        distribution = _mapping(root["distribution"], "distribution")
        _fields(distribution, _DISTRIBUTION_FIELDS, "distribution")
        _stable(distribution["name"], "distribution name")
        _stable(distribution["version"], "distribution version")
        _stable(distribution["wheel"], "distribution wheel")
        _hash64(distribution["wheel_sha256"], "distribution wheel sha256")
        if distribution["runtime_dependencies"] != 0:
            raise SystemIntegrationReceiptError("system integration distribution must have zero runtime dependencies")
        if distribution["package_version_alone_is_identity"] is not False:
            raise SystemIntegrationReceiptError("package version must not be sole system identity")

        verification = _mapping(root["verification"], "verification")
        _fields(verification, _VERIFICATION_FIELDS, "verification")
        for key in (
            "source_focal",
            "deterministic_wheel_bytes",
            "installed_wheel_import",
            "installed_api_identity",
            "installed_complete_causal_registry",
            "installed_complete_semantic_registry",
            "installed_receipt_verifier",
        ):
            if verification[key] != "PASS":
                raise SystemIntegrationReceiptError("required verification is not PASS: " + key)
        for key in ("certify_full", "python_certify_full", "public_release"):
            if verification[key] != "DEFERRED":
                raise SystemIntegrationReceiptError("unexpected deferred verification state: " + key)
        if verification["unity"] != "DEFERRED_BY_PRIORITY":
            raise SystemIntegrationReceiptError("unexpected Unity verification state")

        receipt_hash = _hash64(root["receipt_hash"], "receipt_hash")
        body = {key: value for key, value in root.items() if key != "receipt_hash"}
        if canonical_hash(body) != receipt_hash:
            raise SystemIntegrationReceiptError("system integration receipt canonical hash mismatch")
        object.__setattr__(self, "document", root)

    @property
    def receipt_hash(self) -> str:
        return str(self.document["receipt_hash"])

    @property
    def language_version(self) -> str:
        return str(self.document["language_version"])

    @property
    def system_api_contract_hash(self) -> str:
        return str(self.document["system_api_contract_hash"])

    @property
    def distribution_artifact_sha256(self) -> str:
        return str(_mapping(self.document["distribution"], "distribution")["wheel_sha256"])

    @property
    def source_head(self) -> str:
        return str(_mapping(self.document["source"], "source")["head"])

    @property
    def source_tree(self) -> str:
        return str(_mapping(self.document["source"], "source")["tree"])

    def to_object(self) -> dict[str, object]:
        return dict(self.document)


def build_system_integration_receipt_v0(
    *,
    branch: str,
    head: str,
    tree: str,
    source_date_epoch: str,
    language_version: str,
    system_api_contract_hash: str,
    system_canonical_index_schema: str,
    system_canonical_index_file_sha256: str,
    system_integration_spec_sha256: str,
    distribution_name: str,
    distribution_version: str,
    wheel_name: str,
    wheel_sha256: str,
) -> SystemIntegrationReceiptV0:
    body: dict[str, object] = {
        "schema": SYSTEM_INTEGRATION_RECEIPT_SCHEMA_V0,
        "status": "PASS",
        "source": {
            "branch": branch,
            "head": head,
            "tree": tree,
            "source_date_epoch": source_date_epoch,
        },
        "language_version": language_version,
        "system_api_contract_hash": system_api_contract_hash,
        "system_canonical_index": {
            "schema": system_canonical_index_schema,
            "file_sha256": system_canonical_index_file_sha256,
        },
        "system_integration_spec_sha256": system_integration_spec_sha256,
        "distribution": {
            "name": distribution_name,
            "version": distribution_version,
            "wheel": wheel_name,
            "wheel_sha256": wheel_sha256,
            "runtime_dependencies": 0,
            "package_version_alone_is_identity": False,
        },
        "verification": {
            "source_focal": "PASS",
            "deterministic_wheel_bytes": "PASS",
            "installed_wheel_import": "PASS",
            "installed_api_identity": "PASS",
            "installed_complete_causal_registry": "PASS",
            "installed_complete_semantic_registry": "PASS",
            "installed_receipt_verifier": "PASS",
            "certify_full": "DEFERRED",
            "python_certify_full": "DEFERRED",
            "unity": "DEFERRED_BY_PRIORITY",
            "public_release": "DEFERRED",
        },
    }
    return SystemIntegrationReceiptV0({**body, "receipt_hash": canonical_hash(body)})


def verify_system_integration_receipt_v0(
    receipt: Mapping[str, object],
    *,
    expected_language_version: str,
    expected_system_api_contract_hash: str,
    expected_distribution_artifact_sha256: str,
    expected_source_head: str = "",
    expected_source_tree: str = "",
) -> SystemIntegrationReceiptV0:
    parsed = SystemIntegrationReceiptV0(receipt)
    if parsed.language_version != str(expected_language_version):
        raise SystemIntegrationReceiptError("system integration language version mismatch")
    if parsed.system_api_contract_hash != _hash64(expected_system_api_contract_hash, "expected system api contract hash"):
        raise SystemIntegrationReceiptError("system integration api contract mismatch")
    if parsed.distribution_artifact_sha256 != _hash64(expected_distribution_artifact_sha256, "expected distribution artifact sha256"):
        raise SystemIntegrationReceiptError("system integration distribution artifact mismatch")
    if expected_source_head and parsed.source_head != _git_hash40(expected_source_head, "expected source head"):
        raise SystemIntegrationReceiptError("system integration source head mismatch")
    if expected_source_tree and parsed.source_tree != _git_hash40(expected_source_tree, "expected source tree"):
        raise SystemIntegrationReceiptError("system integration source tree mismatch")
    return parsed


__all__ = [
    "SYSTEM_INTEGRATION_RECEIPT_SCHEMA_V0",
    "SystemIntegrationReceiptError",
    "SystemIntegrationReceiptV0",
    "build_system_integration_receipt_v0",
    "verify_system_integration_receipt_v0",
]
