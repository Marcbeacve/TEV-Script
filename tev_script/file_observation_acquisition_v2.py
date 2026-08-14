from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol, Sequence

from .diagnostics import TevScriptError
from .scoped_filesystem_v2 import open_scoped_root_v2, read_scoped_file_v2
from . import scoped_filesystem_v2 as _shared_file_policy
from .ir_v4_effects import CapabilityContractV4, CapabilityTableV4

FILE_READ_CAPABILITY_ID_V2 = "file.read"
FILE_READ_ACQUISITION_POLICY_V2 = "scoped_snapshot_v1"
FILE_READ_PROVIDER_ID_V2 = "tev.file_read_snapshot"
FILE_READ_PROVIDER_VERSION_V2 = "1.0.0"
MAX_FILE_READ_CALLS_V2 = 1024
MAX_FILE_READ_BYTES_V2 = 1024 * 1024


@dataclass(frozen=True, slots=True)
class FileReadAcquiredCallV2:
    call_index: int
    evidence: dict[str, Any]


class FileReadAcquisitionExecutionStrategyV2(Protocol):
    def run(
        self,
        calls: Sequence[tuple[int, Mapping[str, Any]]],
        acquire_call: Callable[[int, Mapping[str, Any]], FileReadAcquiredCallV2],
    ) -> Sequence[FileReadAcquiredCallV2]: ...


@dataclass(frozen=True, slots=True)
class FileReadObservationProviderDescriptorV2:
    schema: str
    provider_id: str
    provider_version: str
    capability_id: str
    contract_hash: str
    acquisition_policy: str
    maximum_bytes_per_call: int
    implementation_hash: str
    shared_file_policy_hash: str
    descriptor_hash: str


def build_file_read_acquisition_request_v2(
    capabilities: CapabilityTableV4,
    paths: Sequence[str],
) -> dict[str, Any]:
    contract = _require_file_read_contract(capabilities)
    if not isinstance(paths, Sequence) or isinstance(paths, (str, bytes, bytearray)):
        _fail("TEVS_FILE_READ_REQUEST", "file.read acquisition paths must be a sequence")
    if not 1 <= len(paths) <= MAX_FILE_READ_CALLS_V2:
        _fail("TEVS_FILE_READ_REQUEST", f"file.read acquisition requires 1..{MAX_FILE_READ_CALLS_V2} paths")
    calls = []
    for index, value in enumerate(paths):
        if not isinstance(value, str) or not value or "\x00" in value:
            _fail("TEVS_FILE_READ_REQUEST", f"file.read path {index} must be non-empty Text without NUL")
        calls.append({"arguments": [value]})
    payload = {
        "schema": "TEV_SCRIPT_FILE_READ_ACQUISITION_REQUEST_V2_V1",
        "capability_table_hash": capabilities.table_hash,
        "capability_id": contract.capability_id,
        "contract_hash": contract.contract_hash,
        "calls": calls,
    }
    return {**payload, "request_hash": _hash(payload)}


def validate_file_read_acquisition_request_v2(
    raw: Mapping[str, Any],
    capabilities: CapabilityTableV4,
) -> dict[str, Any]:
    item = _object(raw, "file_read_request")
    _exact(item, {"schema", "capability_table_hash", "capability_id", "contract_hash", "calls", "request_hash"}, "file_read_request")
    if item["schema"] != "TEV_SCRIPT_FILE_READ_ACQUISITION_REQUEST_V2_V1":
        _fail("TEVS_FILE_READ_REQUEST_SCHEMA", "unsupported file.read acquisition request schema")
    contract = _require_file_read_contract(capabilities)
    if item["capability_table_hash"] != capabilities.table_hash:
        _fail("TEVS_FILE_READ_REQUEST_CONTRACT", "file.read request capability table hash mismatch")
    if item["capability_id"] != contract.capability_id or item["contract_hash"] != contract.contract_hash:
        _fail("TEVS_FILE_READ_REQUEST_CONTRACT", "file.read request contract mismatch")
    calls = item["calls"]
    if not isinstance(calls, list) or not 1 <= len(calls) <= MAX_FILE_READ_CALLS_V2:
        _fail("TEVS_FILE_READ_REQUEST", "file.read request calls must be a bounded non-empty array")
    canonical_calls = []
    for index, raw_call in enumerate(calls):
        call = _object(raw_call, f"file_read_request.calls[{index}]")
        _exact(call, {"arguments"}, f"file_read_request.calls[{index}]")
        args = call["arguments"]
        if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], str) or not args[0] or "\x00" in args[0]:
            _fail("TEVS_FILE_READ_REQUEST", f"file.read request call {index} must contain exactly one Text path")
        canonical_calls.append({"arguments": [args[0]]})
    payload = {
        "schema": item["schema"],
        "capability_table_hash": capabilities.table_hash,
        "capability_id": contract.capability_id,
        "contract_hash": contract.contract_hash,
        "calls": canonical_calls,
    }
    if item["request_hash"] != _hash(payload):
        _fail("TEVS_FILE_READ_REQUEST_HASH", "file.read acquisition request hash mismatch")
    return {**payload, "request_hash": item["request_hash"]}


def build_file_read_provider_descriptor_v2(
    contract: CapabilityContractV4,
) -> FileReadObservationProviderDescriptorV2:
    _require_file_read_signature(contract)
    implementation_hash, shared_hash = _implementation_hashes()
    payload = {
        "schema": "TEV_SCRIPT_FILE_READ_PROVIDER_DESCRIPTOR_V2_V1",
        "provider_id": FILE_READ_PROVIDER_ID_V2,
        "provider_version": FILE_READ_PROVIDER_VERSION_V2,
        "capability_id": contract.capability_id,
        "contract_hash": contract.contract_hash,
        "acquisition_policy": FILE_READ_ACQUISITION_POLICY_V2,
        "maximum_bytes_per_call": MAX_FILE_READ_BYTES_V2,
        "implementation_hash": implementation_hash,
        "shared_file_policy_hash": shared_hash,
    }
    return FileReadObservationProviderDescriptorV2(
        payload["schema"],
        payload["provider_id"],
        payload["provider_version"],
        payload["capability_id"],
        payload["contract_hash"],
        payload["acquisition_policy"],
        payload["maximum_bytes_per_call"],
        implementation_hash,
        shared_hash,
        _hash(payload),
    )


def file_read_provider_descriptor_to_dict_v2(
    descriptor: FileReadObservationProviderDescriptorV2,
) -> dict[str, Any]:
    if not isinstance(descriptor, FileReadObservationProviderDescriptorV2):
        _fail("TEVS_FILE_READ_PROVIDER", "expected FileReadObservationProviderDescriptorV2")
    payload = {
        "schema": descriptor.schema,
        "provider_id": descriptor.provider_id,
        "provider_version": descriptor.provider_version,
        "capability_id": descriptor.capability_id,
        "contract_hash": descriptor.contract_hash,
        "acquisition_policy": descriptor.acquisition_policy,
        "maximum_bytes_per_call": descriptor.maximum_bytes_per_call,
        "implementation_hash": descriptor.implementation_hash,
        "shared_file_policy_hash": descriptor.shared_file_policy_hash,
    }
    if descriptor.descriptor_hash != _hash(payload):
        _fail("TEVS_FILE_READ_PROVIDER_HASH", "file.read provider descriptor hash mismatch")
    return {**payload, "descriptor_hash": descriptor.descriptor_hash}


def acquire_file_read_observations_v2(
    request_raw: Mapping[str, Any],
    capabilities: CapabilityTableV4,
    root: str | os.PathLike[str],
    *,
    execution_strategy: FileReadAcquisitionExecutionStrategyV2 | None = None,
) -> dict[str, Any]:
    request = validate_file_read_acquisition_request_v2(request_raw, capabilities)
    contract = _require_file_read_contract(capabilities)
    descriptor = build_file_read_provider_descriptor_v2(contract)
    descriptor_wire = file_read_provider_descriptor_to_dict_v2(descriptor)
    try:
        filesystem = open_scoped_root_v2(root)
    except TevScriptError as error:
        _raise_scoped_read_error(error)
    try:
        scope_hash = filesystem.scope_hash

        def acquire_call(index: int, request_call: Mapping[str, Any]) -> FileReadAcquiredCallV2:
            requested_path = request_call["arguments"][0]
            try:
                observed = read_scoped_file_v2(
                    filesystem,
                    requested_path,
                    maximum_bytes=MAX_FILE_READ_BYTES_V2,
                )
            except TevScriptError as error:
                _raise_scoped_read_error(error)
            data = observed.data
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError as error:
                _fail("TEVS_FILE_READ_UTF8", f"file.read content must be valid UTF-8: {error}")
            arguments_hash = _hash({
                "schema": "TEV_SCRIPT_FILE_READ_ARGUMENTS_V2_V1",
                "arguments": [requested_path],
            })
            call_payload = {
                "schema": "TEV_SCRIPT_FILE_READ_ACQUISITION_CALL_V2_V1",
                "call_index": index,
                "capability_id": contract.capability_id,
                "contract_hash": contract.contract_hash,
                "arguments": [requested_path],
                "arguments_hash": arguments_hash,
                "canonical_relative_path": observed.canonical_relative_path,
                "return": text,
                "content_sha256": observed.content_sha256,
                "byte_count": len(data),
                "provider_descriptor_hash": descriptor.descriptor_hash,
                "authority_scope_hash": scope_hash,
                "acquisition_policy": FILE_READ_ACQUISITION_POLICY_V2,
            }
            return FileReadAcquiredCallV2(
                index,
                {**call_payload, "call_evidence_hash": _hash(call_payload)},
            )

        indexed_calls = tuple(enumerate(request["calls"]))
        completed = (
            tuple(acquire_call(index, call) for index, call in indexed_calls)
            if execution_strategy is None
            else tuple(execution_strategy.run(indexed_calls, acquire_call))
        )
    finally:
        filesystem.close()
    if len(completed) != len(indexed_calls) or any(not isinstance(item, FileReadAcquiredCallV2) for item in completed):
        _fail("TEVS_FILE_READ_ACQUISITION_STRATEGY", "file.read acquisition strategy returned an invalid result set")
    by_index = {item.call_index: item for item in completed}
    if len(by_index) != len(completed) or set(by_index) != set(range(len(indexed_calls))):
        _fail("TEVS_FILE_READ_ACQUISITION_STRATEGY", "file.read acquisition strategy changed the canonical call-index set")
    calls: list[dict[str, Any]] = []
    for index in range(len(indexed_calls)):
        item = by_index[index]
        if item.evidence.get("call_index") != index:
            _fail("TEVS_FILE_READ_ACQUISITION_STRATEGY", "file.read acquisition result call_index mismatch")
        calls.append(dict(item.evidence))

    payload = {
        "schema": "TEV_SCRIPT_FILE_READ_ACQUISITION_EVIDENCE_V2_V1",
        "request_hash": request["request_hash"],
        "capability_table_hash": capabilities.table_hash,
        "capability_id": contract.capability_id,
        "contract_hash": contract.contract_hash,
        "provider": descriptor_wire,
        "authority_scope_hash": scope_hash,
        "acquisition_policy": FILE_READ_ACQUISITION_POLICY_V2,
        "calls": calls,
    }
    return {**payload, "evidence_hash": _hash(payload)}


def validate_file_read_acquisition_evidence_v2(
    raw: Mapping[str, Any],
    capabilities: CapabilityTableV4,
    *,
    expected_authority_scope_hash: str | None = None,
    expected_provider_descriptor_hash: str | None = None,
) -> dict[str, Any]:
    item = _object(raw, "file_read_evidence")
    _exact(item, {"schema", "request_hash", "capability_table_hash", "capability_id", "contract_hash", "provider", "authority_scope_hash", "acquisition_policy", "calls", "evidence_hash"}, "file_read_evidence")
    if item["schema"] != "TEV_SCRIPT_FILE_READ_ACQUISITION_EVIDENCE_V2_V1":
        _fail("TEVS_FILE_READ_EVIDENCE_SCHEMA", "unsupported file.read acquisition evidence schema")
    contract = _require_file_read_contract(capabilities)
    if item["capability_table_hash"] != capabilities.table_hash or item["capability_id"] != contract.capability_id or item["contract_hash"] != contract.contract_hash:
        _fail("TEVS_FILE_READ_EVIDENCE_CONTRACT", "file.read acquisition evidence contract mismatch")
    if item["acquisition_policy"] != FILE_READ_ACQUISITION_POLICY_V2:
        _fail("TEVS_FILE_READ_EVIDENCE_POLICY", "unsupported file.read acquisition policy")
    provider = _validate_provider_wire(item["provider"], contract)
    scope_hash = _sha(item["authority_scope_hash"], "file_read_evidence.authority_scope_hash")
    if expected_authority_scope_hash is not None and scope_hash != expected_authority_scope_hash:
        _fail("TEVS_FILE_READ_EVIDENCE_SCOPE", "file.read evidence authority scope pin mismatch")
    if expected_provider_descriptor_hash is not None and provider["descriptor_hash"] != expected_provider_descriptor_hash:
        _fail("TEVS_FILE_READ_EVIDENCE_PROVIDER", "file.read evidence provider descriptor pin mismatch")
    calls_raw = item["calls"]
    if not isinstance(calls_raw, list) or not 1 <= len(calls_raw) <= MAX_FILE_READ_CALLS_V2:
        _fail("TEVS_FILE_READ_EVIDENCE", "file.read evidence calls must be a bounded non-empty array")
    calls: list[dict[str, Any]] = []
    for index, raw_call in enumerate(calls_raw):
        call = _object(raw_call, f"file_read_evidence.calls[{index}]")
        expected_fields = {"schema", "call_index", "capability_id", "contract_hash", "arguments", "arguments_hash", "canonical_relative_path", "return", "content_sha256", "byte_count", "provider_descriptor_hash", "authority_scope_hash", "acquisition_policy", "call_evidence_hash"}
        _exact(call, expected_fields, f"file_read_evidence.calls[{index}]")
        if call["schema"] != "TEV_SCRIPT_FILE_READ_ACQUISITION_CALL_V2_V1" or call["call_index"] != index:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence call order/schema mismatch")
        if call["capability_id"] != contract.capability_id or call["contract_hash"] != contract.contract_hash:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence call contract mismatch")
        args = call["arguments"]
        if not isinstance(args, list) or len(args) != 1 or not isinstance(args[0], str) or not args[0]:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence call requires one Text argument")
        arguments_hash = _hash({"schema": "TEV_SCRIPT_FILE_READ_ARGUMENTS_V2_V1", "arguments": [args[0]]})
        if call["arguments_hash"] != arguments_hash:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence arguments hash mismatch")
        if not isinstance(call["canonical_relative_path"], str) or not call["canonical_relative_path"]:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence canonical path must be non-empty Text")
        if not isinstance(call["return"], str):
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence return must be Text")
        content_bytes = call["return"].encode("utf-8")
        if call["byte_count"] != len(content_bytes) or call["content_sha256"] != hashlib.sha256(content_bytes).hexdigest():
            _fail("TEVS_FILE_READ_EVIDENCE_CONTENT", "file.read evidence content witness mismatch")
        if call["provider_descriptor_hash"] != provider["descriptor_hash"] or call["authority_scope_hash"] != scope_hash or call["acquisition_policy"] != FILE_READ_ACQUISITION_POLICY_V2:
            _fail("TEVS_FILE_READ_EVIDENCE_CALL", "file.read evidence call provenance mismatch")
        call_payload = {key: call[key] for key in expected_fields if key != "call_evidence_hash"}
        if call["call_evidence_hash"] != _hash(call_payload):
            _fail("TEVS_FILE_READ_EVIDENCE_CALL_HASH", "file.read call evidence hash mismatch")
        calls.append(dict(call))
    payload = {
        "schema": item["schema"],
        "request_hash": _sha(item["request_hash"], "file_read_evidence.request_hash"),
        "capability_table_hash": capabilities.table_hash,
        "capability_id": contract.capability_id,
        "contract_hash": contract.contract_hash,
        "provider": provider,
        "authority_scope_hash": scope_hash,
        "acquisition_policy": FILE_READ_ACQUISITION_POLICY_V2,
        "calls": calls,
    }
    if item["evidence_hash"] != _hash(payload):
        _fail("TEVS_FILE_READ_EVIDENCE_HASH", "file.read acquisition evidence hash mismatch")
    return {**payload, "evidence_hash": item["evidence_hash"]}


def scenario_from_file_read_evidence_v2(
    evidence_raw: Mapping[str, Any],
    capabilities: CapabilityTableV4,
) -> dict[str, Any]:
    evidence = validate_file_read_acquisition_evidence_v2(evidence_raw, capabilities)
    return {
        "capability_table_hash": capabilities.table_hash,
        "capabilities": [{
            "capability_id": evidence["capability_id"],
            "contract_hash": evidence["contract_hash"],
            "calls": [
                {"arguments": call["arguments"], "return": call["return"]}
                for call in evidence["calls"]
            ],
        }],
    }


def _validate_provider_wire(raw: Mapping[str, Any], contract: CapabilityContractV4) -> dict[str, Any]:
    item = _object(raw, "file_read_evidence.provider")
    expected = {"schema", "provider_id", "provider_version", "capability_id", "contract_hash", "acquisition_policy", "maximum_bytes_per_call", "implementation_hash", "shared_file_policy_hash", "descriptor_hash"}
    _exact(item, expected, "file_read_evidence.provider")
    payload = {key: item[key] for key in expected if key != "descriptor_hash"}
    if item["schema"] != "TEV_SCRIPT_FILE_READ_PROVIDER_DESCRIPTOR_V2_V1" or item["provider_id"] != FILE_READ_PROVIDER_ID_V2 or item["provider_version"] != FILE_READ_PROVIDER_VERSION_V2:
        _fail("TEVS_FILE_READ_PROVIDER", "unsupported file.read provider descriptor")
    if item["capability_id"] != contract.capability_id or item["contract_hash"] != contract.contract_hash:
        _fail("TEVS_FILE_READ_PROVIDER", "file.read provider contract mismatch")
    if item["acquisition_policy"] != FILE_READ_ACQUISITION_POLICY_V2 or item["maximum_bytes_per_call"] != MAX_FILE_READ_BYTES_V2:
        _fail("TEVS_FILE_READ_PROVIDER", "file.read provider policy/budget mismatch")
    _sha(item["implementation_hash"], "file_read_provider.implementation_hash")
    _sha(item["shared_file_policy_hash"], "file_read_provider.shared_file_policy_hash")
    if item["descriptor_hash"] != _hash(payload):
        _fail("TEVS_FILE_READ_PROVIDER_HASH", "file.read provider descriptor hash mismatch")
    return dict(item)


def _require_file_read_contract(capabilities: CapabilityTableV4) -> CapabilityContractV4:
    if not isinstance(capabilities, CapabilityTableV4):
        _fail("TEVS_FILE_READ_CONTRACT", "file.read acquisition requires CapabilityTableV4")
    contract = capabilities.require(FILE_READ_CAPABILITY_ID_V2)
    _require_file_read_signature(contract)
    return contract


def _require_file_read_signature(contract: CapabilityContractV4) -> None:
    if contract.capability_id != FILE_READ_CAPABILITY_ID_V2 or contract.parameter_type_ids != ("Text",) or contract.return_type_id != "Text" or contract.kind != "observation":
        _fail("TEVS_FILE_READ_CONTRACT", "file.read acquisition requires observation file.read(Text)->Text")


def _implementation_hashes() -> tuple[str, str]:
    try:
        own = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        shared = hashlib.sha256(Path(_shared_file_policy.__file__).read_bytes()).hexdigest()
    except OSError as error:
        _fail("TEVS_FILE_READ_IMPLEMENTATION", f"file.read provider implementation bytes are unreadable: {error}")
    combined = _hash({
        "schema": "TEV_SCRIPT_FILE_READ_IMPLEMENTATION_CLOSURE_V2_V1",
        "module_sha256": own,
        "shared_file_policy_sha256": shared,
    })
    return combined, shared


def _raise_scoped_read_error(error: TevScriptError) -> None:
    code = error.diagnostic.code
    if code == "TEVS_SCOPED_FS_BUDGET":
        _fail("TEVS_FILE_READ_BUDGET", error.diagnostic.message)
    if code == "TEVS_SCOPED_FS_ESCAPE":
        _fail("TEVS_FILE_READ_PATH_ESCAPE", error.diagnostic.message)
    if code in {"TEVS_SCOPED_FS_PATH", "TEVS_SCOPED_FS_KIND", "TEVS_SCOPED_FS_ROOT"}:
        _fail("TEVS_FILE_READ_PATH", error.diagnostic.message)
    _fail("TEVS_FILE_READ_IO", error.diagnostic.message)


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_FILE_READ_SHAPE", f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        _fail("TEVS_FILE_READ_SHAPE", f"{path} field set mismatch: {sorted(set(value) ^ expected)}")


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_FILE_READ_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
