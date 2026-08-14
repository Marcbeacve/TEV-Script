from __future__ import annotations

from dataclasses import dataclass
import hashlib
import ipaddress
import json
from pathlib import Path
import re
import ssl
from typing import Any, Mapping, Protocol, Sequence
import urllib.error
import urllib.parse
import urllib.request

from .diagnostics import TevScriptError
from .module_linker_v2 import (
    MAX_MODULES_V2,
    MAX_MODULE_SOURCE_BYTES_V2,
    build_module_bundle_v2,
    parse_pure_module_v2,
    validate_module_bundle_v2,
)

REMOTE_MODULE_TRANSPORT_POLICY_V2 = "https_direct_no_proxy_no_redirect_content_pinned_v1"
REMOTE_MODULE_ACQUISITION_POLICY_V2 = "build_time_content_pinned_v1"
REMOTE_MODULE_PROVIDER_ID_V2 = "tev.urllib_https_module_fetch"
REMOTE_MODULE_PROVIDER_VERSION_V2 = "1.0.0"
_MODULE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*$")
_PROVIDER_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.-]*$")


@dataclass(frozen=True, slots=True)
class RemoteModuleTransportDescriptorV2:
    schema: str
    provider_id: str
    provider_version: str
    transport_policy: str
    maximum_response_bytes: int
    implementation_hash: str
    descriptor_hash: str


@dataclass(frozen=True, slots=True)
class RemoteModuleFetchResponseV2:
    final_url: str
    status_code: int
    body: bytes


class RemoteModuleTransportV2(Protocol):
    descriptor: RemoteModuleTransportDescriptorV2

    def fetch(self, canonical_url: str, *, maximum_bytes: int) -> RemoteModuleFetchResponseV2:
        ...


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


class UrllibHttpsModuleTransportV2:
    def __init__(self) -> None:
        self.descriptor = build_remote_module_transport_descriptor_v2(
            provider_id=REMOTE_MODULE_PROVIDER_ID_V2,
            provider_version=REMOTE_MODULE_PROVIDER_VERSION_V2,
            implementation_hash=_implementation_hash(),
            maximum_response_bytes=MAX_MODULE_SOURCE_BYTES_V2,
        )

    def fetch(self, canonical_url: str, *, maximum_bytes: int) -> RemoteModuleFetchResponseV2:
        canonical = canonical_remote_module_url_v2(canonical_url)
        if not isinstance(maximum_bytes, int) or isinstance(maximum_bytes, bool) or not 1 <= maximum_bytes <= self.descriptor.maximum_response_bytes:
            _fail("TEVS_V2_REMOTE_MODULE_BUDGET", "remote module fetch maximum_bytes exceeds provider policy")
        request = urllib.request.Request(
            canonical,
            headers={"Accept": "text/plain, application/octet-stream;q=0.5", "User-Agent": "TEV-Script/2.0 remote-module-acquisition-r1"},
            method="GET",
        )
        context = ssl.create_default_context()
        opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}),
            urllib.request.HTTPSHandler(context=context),
            _NoRedirectHandler(),
        )
        try:
            with opener.open(request, timeout=30) as response:
                status = int(getattr(response, "status", response.getcode()))
                final_url = canonical_remote_module_url_v2(response.geturl())
                raw_length = response.headers.get("Content-Length")
                if raw_length is not None:
                    try:
                        declared = int(raw_length, 10)
                    except ValueError:
                        _fail("TEVS_V2_REMOTE_MODULE_HTTP", "remote module Content-Length must be an integer when present")
                    if declared < 0 or declared > maximum_bytes:
                        _fail("TEVS_V2_REMOTE_MODULE_BUDGET", "remote module Content-Length exceeds acquisition budget")
                body = response.read(maximum_bytes + 1)
        except TevScriptError:
            raise
        except urllib.error.HTTPError as error:
            _fail("TEVS_V2_REMOTE_MODULE_HTTP", f"remote module HTTP status {error.code}")
        except (urllib.error.URLError, TimeoutError, OSError, ssl.SSLError) as error:
            _fail("TEVS_V2_REMOTE_MODULE_NETWORK", f"remote module acquisition transport failed: {type(error).__name__}: {error}")
        if status != 200:
            _fail("TEVS_V2_REMOTE_MODULE_HTTP", f"remote module requires HTTP 200, got {status}")
        if final_url != canonical:
            _fail("TEVS_V2_REMOTE_MODULE_REDIRECT", "remote module final URL differs from pinned canonical URL")
        if len(body) > maximum_bytes:
            _fail("TEVS_V2_REMOTE_MODULE_BUDGET", "remote module response exceeds acquisition budget")
        return RemoteModuleFetchResponseV2(final_url, status, body)


def canonical_remote_module_url_v2(value: str) -> str:
    if not isinstance(value, str) or not value or any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module URL must be non-empty Text without control characters")
    try:
        split = urllib.parse.urlsplit(value)
    except ValueError as error:
        _fail("TEVS_V2_REMOTE_MODULE_URL", f"invalid remote module URL: {error}")
    if split.scheme.lower() != "https":
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module R1 permits HTTPS only")
    if split.username is not None or split.password is not None:
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module URL cannot contain userinfo credentials")
    if split.query or split.fragment:
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module R1 forbids URL query and fragment")
    host = split.hostname
    if not host:
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module HTTPS URL requires a host")
    try:
        ip = ipaddress.ip_address(host)
        canonical_host = f"[{ip.compressed}]" if ip.version == 6 else ip.compressed
    except ValueError:
        try:
            canonical_host = host.encode("idna").decode("ascii").lower()
        except UnicodeError as error:
            _fail("TEVS_V2_REMOTE_MODULE_URL", f"remote module host cannot be canonicalized: {error}")
    try:
        port = split.port
    except ValueError as error:
        _fail("TEVS_V2_REMOTE_MODULE_URL", f"invalid remote module port: {error}")
    if port not in (None, 443):
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module R1 permits only the default HTTPS port 443")
    path = split.path or "/"
    if not path.startswith("/") or "\\" in path:
        _fail("TEVS_V2_REMOTE_MODULE_URL", "remote module URL path must be absolute and cannot contain backslashes")
    netloc = canonical_host
    return urllib.parse.urlunsplit(("https", netloc, path, "", ""))


def build_remote_module_transport_descriptor_v2(
    *,
    provider_id: str,
    provider_version: str,
    implementation_hash: str,
    maximum_response_bytes: int,
) -> RemoteModuleTransportDescriptorV2:
    if not isinstance(provider_id, str) or _PROVIDER_ID.fullmatch(provider_id) is None:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "remote module provider_id is invalid")
    if not isinstance(provider_version, str) or not provider_version:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "remote module provider_version must be non-empty Text")
    implementation_hash = _sha(implementation_hash, "remote_module_provider.implementation_hash")
    if not isinstance(maximum_response_bytes, int) or isinstance(maximum_response_bytes, bool) or not 1 <= maximum_response_bytes <= MAX_MODULE_SOURCE_BYTES_V2:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "remote module provider maximum_response_bytes is invalid")
    payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_TRANSPORT_DESCRIPTOR_V2_R1",
        "provider_id": provider_id,
        "provider_version": provider_version,
        "transport_policy": REMOTE_MODULE_TRANSPORT_POLICY_V2,
        "maximum_response_bytes": maximum_response_bytes,
        "implementation_hash": implementation_hash,
    }
    return RemoteModuleTransportDescriptorV2(
        payload["schema"], provider_id, provider_version, payload["transport_policy"],
        maximum_response_bytes, implementation_hash, _hash(payload)
    )


def remote_module_transport_descriptor_to_dict_v2(descriptor: RemoteModuleTransportDescriptorV2) -> dict[str, Any]:
    _validate_transport_descriptor(descriptor)
    return {
        "schema": descriptor.schema,
        "provider_id": descriptor.provider_id,
        "provider_version": descriptor.provider_version,
        "transport_policy": descriptor.transport_policy,
        "maximum_response_bytes": descriptor.maximum_response_bytes,
        "implementation_hash": descriptor.implementation_hash,
        "descriptor_hash": descriptor.descriptor_hash,
    }


def build_remote_module_manifest_v2(entries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes, bytearray)) or not 1 <= len(entries) <= MAX_MODULES_V2:
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", f"remote module manifest requires 1..{MAX_MODULES_V2} entries")
    normalized = []
    seen: set[str] = set()
    for index, raw in enumerate(entries):
        if not isinstance(raw, Mapping) or set(raw) != {"module_id", "url", "expected_sha256"}:
            _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", f"remote module manifest entry {index} field set mismatch")
        module_id = raw["module_id"]
        if not isinstance(module_id, str) or _MODULE_ID.fullmatch(module_id) is None:
            _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", f"invalid remote module id at entry {index}")
        if module_id in seen:
            _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", f"duplicate remote module id {module_id!r}")
        seen.add(module_id)
        url = canonical_remote_module_url_v2(raw["url"])
        expected = _sha(raw["expected_sha256"], f"remote_module_manifest[{module_id}].expected_sha256")
        entry_payload = {
            "schema": "TEV_SCRIPT_REMOTE_MODULE_MANIFEST_ENTRY_V2_R1",
            "module_id": module_id,
            "canonical_url": url,
            "expected_sha256": expected,
        }
        normalized.append({**entry_payload, "entry_hash": _hash(entry_payload)})
    normalized.sort(key=lambda item: item["module_id"])
    payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_MANIFEST_V2_R1",
        "acquisition_policy": REMOTE_MODULE_ACQUISITION_POLICY_V2,
        "entries": normalized,
    }
    return {**payload, "manifest_hash": _hash(payload)}


def validate_remote_module_manifest_v2(raw: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {"schema", "acquisition_policy", "entries", "manifest_hash"}:
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", "remote module manifest root field set mismatch")
    if raw["schema"] != "TEV_SCRIPT_REMOTE_MODULE_MANIFEST_V2_R1" or raw["acquisition_policy"] != REMOTE_MODULE_ACQUISITION_POLICY_V2:
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", "unsupported remote module manifest schema/policy")
    entries = raw["entries"]
    if not isinstance(entries, list) or not 1 <= len(entries) <= MAX_MODULES_V2:
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST", "remote module manifest entries must be a bounded non-empty array")
    rebuilt = build_remote_module_manifest_v2([
        {"module_id": item.get("module_id"), "url": item.get("canonical_url"), "expected_sha256": item.get("expected_sha256")}
        if isinstance(item, Mapping) else {}
        for item in entries
    ])
    if rebuilt != dict(raw):
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST_HASH", "remote module manifest is not canonical or hash-valid")
    return rebuilt


def acquire_remote_module_bundle_v2(
    manifest_raw: Mapping[str, Any],
    transport: RemoteModuleTransportV2,
) -> dict[str, Any]:
    manifest = validate_remote_module_manifest_v2(manifest_raw)
    descriptor = getattr(transport, "descriptor", None)
    _validate_transport_descriptor(descriptor)
    descriptor_wire = remote_module_transport_descriptor_to_dict_v2(descriptor)
    sources: dict[str, str] = {}
    evidence_entries: list[dict[str, Any]] = []
    for entry in manifest["entries"]:
        try:
            response = transport.fetch(entry["canonical_url"], maximum_bytes=min(MAX_MODULE_SOURCE_BYTES_V2, descriptor.maximum_response_bytes))
        except TevScriptError:
            raise
        except Exception as error:
            _fail("TEVS_V2_REMOTE_MODULE_TRANSPORT", f"remote module transport raised {type(error).__name__}: {error}")
        if not isinstance(response, RemoteModuleFetchResponseV2):
            _fail("TEVS_V2_REMOTE_MODULE_TRANSPORT", "remote module transport must return RemoteModuleFetchResponseV2")
        final_url = canonical_remote_module_url_v2(response.final_url)
        if final_url != entry["canonical_url"]:
            _fail("TEVS_V2_REMOTE_MODULE_REDIRECT", "remote module transport returned a different final URL")
        if response.status_code != 200:
            _fail("TEVS_V2_REMOTE_MODULE_HTTP", f"remote module requires status 200, got {response.status_code}")
        if not isinstance(response.body, bytes) or len(response.body) > descriptor.maximum_response_bytes or len(response.body) > MAX_MODULE_SOURCE_BYTES_V2:
            _fail("TEVS_V2_REMOTE_MODULE_BUDGET", "remote module body exceeds acquisition budget or is not bytes")
        actual_sha = hashlib.sha256(response.body).hexdigest()
        if actual_sha != entry["expected_sha256"]:
            _fail("TEVS_V2_REMOTE_MODULE_CONTENT_PIN", f"remote module {entry['module_id']!r} SHA-256 does not match manifest pin")
        try:
            source = response.body.decode("utf-8")
        except UnicodeDecodeError as error:
            _fail("TEVS_V2_REMOTE_MODULE_UTF8", f"remote module {entry['module_id']!r} must be valid UTF-8: {error}")
        parsed = parse_pure_module_v2(source)
        if parsed.module_id != entry["module_id"]:
            _fail("TEVS_V2_REMOTE_MODULE_ID", f"acquired module declares {parsed.module_id!r}, expected {entry['module_id']!r}")
        sources[entry["module_id"]] = source
        evidence_payload = {
            "schema": "TEV_SCRIPT_REMOTE_MODULE_ACQUISITION_ENTRY_V2_R1",
            "module_id": entry["module_id"],
            "manifest_entry_hash": entry["entry_hash"],
            "canonical_url": entry["canonical_url"],
            "expected_sha256": entry["expected_sha256"],
            "actual_sha256": actual_sha,
            "byte_count": len(response.body),
            "source": source,
            "status_code": response.status_code,
            "final_url": final_url,
            "transport_descriptor_hash": descriptor.descriptor_hash,
            "transport_policy": descriptor.transport_policy,
        }
        evidence_entries.append({**evidence_payload, "entry_evidence_hash": _hash(evidence_payload)})
    evidence_entries.sort(key=lambda item: item["module_id"])
    bundle = build_module_bundle_v2(sources)
    evidence_payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_ACQUISITION_EVIDENCE_V2_R1",
        "manifest_hash": manifest["manifest_hash"],
        "acquisition_policy": REMOTE_MODULE_ACQUISITION_POLICY_V2,
        "transport": descriptor_wire,
        "entries": evidence_entries,
        "module_bundle_hash": bundle["bundle_hash"],
        "module_lock_hash": bundle["lock"]["lock_hash"],
    }
    evidence = {**evidence_payload, "evidence_hash": _hash(evidence_payload)}
    result_payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_ACQUISITION_RESULT_V2_R1",
        "manifest": manifest,
        "evidence": evidence,
        "bundle": bundle,
    }
    return {**result_payload, "result_hash": _hash(result_payload)}


def validate_remote_module_acquisition_result_v2(
    raw: Mapping[str, Any],
    *,
    expected_transport_descriptor_hash: str | None = None,
    expected_manifest_hash: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {"schema", "manifest", "evidence", "bundle", "result_hash"}:
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module acquisition result field set mismatch")
    if raw["schema"] != "TEV_SCRIPT_REMOTE_MODULE_ACQUISITION_RESULT_V2_R1":
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "unsupported remote module acquisition result schema")
    manifest = validate_remote_module_manifest_v2(raw["manifest"])
    if expected_manifest_hash is not None and manifest["manifest_hash"] != _sha(expected_manifest_hash, "expected_manifest_hash"):
        _fail("TEVS_V2_REMOTE_MODULE_MANIFEST_PIN", "remote module manifest hash pin mismatch")
    evidence = _validate_acquisition_evidence(raw["evidence"], manifest, expected_transport_descriptor_hash=expected_transport_descriptor_hash)
    bundle = validate_module_bundle_v2(raw["bundle"])
    if evidence["module_bundle_hash"] != bundle["bundle_hash"] or evidence["module_lock_hash"] != bundle["lock"]["lock_hash"]:
        _fail("TEVS_V2_REMOTE_MODULE_BUNDLE_BINDING", "remote module evidence does not bind the supplied module bundle")
    sources_from_evidence = {item["module_id"]: item["source"] for item in evidence["entries"]}
    rebuilt_bundle = build_module_bundle_v2(sources_from_evidence)
    if rebuilt_bundle != bundle:
        _fail("TEVS_V2_REMOTE_MODULE_BUNDLE_BINDING", "remote module bundle differs from acquired evidence sources")
    payload = {"schema": raw["schema"], "manifest": manifest, "evidence": evidence, "bundle": bundle}
    if raw["result_hash"] != _hash(payload):
        _fail("TEVS_V2_REMOTE_MODULE_RESULT_HASH", "remote module acquisition result hash mismatch")
    return {**payload, "result_hash": raw["result_hash"]}


def _validate_acquisition_evidence(
    raw: Mapping[str, Any],
    manifest: Mapping[str, Any],
    *,
    expected_transport_descriptor_hash: str | None,
) -> dict[str, Any]:
    expected_fields = {"schema", "manifest_hash", "acquisition_policy", "transport", "entries", "module_bundle_hash", "module_lock_hash", "evidence_hash"}
    if not isinstance(raw, Mapping) or set(raw) != expected_fields:
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module acquisition evidence field set mismatch")
    if raw["schema"] != "TEV_SCRIPT_REMOTE_MODULE_ACQUISITION_EVIDENCE_V2_R1" or raw["acquisition_policy"] != REMOTE_MODULE_ACQUISITION_POLICY_V2:
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "unsupported remote module evidence schema/policy")
    if raw["manifest_hash"] != manifest["manifest_hash"]:
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module evidence manifest hash mismatch")
    transport = _validate_transport_descriptor_wire(raw["transport"])
    if expected_transport_descriptor_hash is not None and transport["descriptor_hash"] != _sha(expected_transport_descriptor_hash, "expected_transport_descriptor_hash"):
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER_PIN", "remote module transport descriptor pin mismatch")
    entries = raw["entries"]
    if not isinstance(entries, list) or len(entries) != len(manifest["entries"]):
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module evidence entry count mismatch")
    manifest_by_id = {item["module_id"]: item for item in manifest["entries"]}
    previous: str | None = None
    canonical_entries = []
    for index, item in enumerate(entries):
        fields = {"schema", "module_id", "manifest_entry_hash", "canonical_url", "expected_sha256", "actual_sha256", "byte_count", "source", "status_code", "final_url", "transport_descriptor_hash", "transport_policy", "entry_evidence_hash"}
        if not isinstance(item, Mapping) or set(item) != fields:
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", f"remote module evidence entry {index} field set mismatch")
        module_id = item["module_id"]
        if not isinstance(module_id, str) or _MODULE_ID.fullmatch(module_id) is None or (previous is not None and module_id <= previous):
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module evidence entries must be strictly sorted by module id")
        previous = module_id
        expected = manifest_by_id.get(module_id)
        if expected is None or item["manifest_entry_hash"] != expected["entry_hash"] or item["canonical_url"] != expected["canonical_url"] or item["expected_sha256"] != expected["expected_sha256"]:
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", f"remote module evidence entry {module_id!r} diverges from manifest")
        if item["status_code"] != 200 or item["final_url"] != expected["canonical_url"]:
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", f"remote module evidence entry {module_id!r} transport witness mismatch")
        source = item["source"]
        if not isinstance(source, str):
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", "remote module evidence source must be Text")
        data = source.encode("utf-8")
        actual_sha = hashlib.sha256(data).hexdigest()
        if item["byte_count"] != len(data) or item["actual_sha256"] != actual_sha or actual_sha != expected["expected_sha256"]:
            _fail("TEVS_V2_REMOTE_MODULE_CONTENT_PIN", f"remote module evidence content witness mismatch for {module_id!r}")
        if item["transport_descriptor_hash"] != transport["descriptor_hash"] or item["transport_policy"] != transport["transport_policy"]:
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE", f"remote module evidence transport provenance mismatch for {module_id!r}")
        parsed = parse_pure_module_v2(source)
        if parsed.module_id != module_id:
            _fail("TEVS_V2_REMOTE_MODULE_ID", f"remote module evidence source declares {parsed.module_id!r}, expected {module_id!r}")
        payload = {key: item[key] for key in fields if key != "entry_evidence_hash"}
        if item["entry_evidence_hash"] != _hash(payload):
            _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE_HASH", f"remote module entry evidence hash mismatch for {module_id!r}")
        canonical_entries.append(dict(item))
    payload = {
        "schema": raw["schema"],
        "manifest_hash": manifest["manifest_hash"],
        "acquisition_policy": REMOTE_MODULE_ACQUISITION_POLICY_V2,
        "transport": transport,
        "entries": canonical_entries,
        "module_bundle_hash": _sha(raw["module_bundle_hash"], "remote_module_evidence.module_bundle_hash"),
        "module_lock_hash": _sha(raw["module_lock_hash"], "remote_module_evidence.module_lock_hash"),
    }
    if raw["evidence_hash"] != _hash(payload):
        _fail("TEVS_V2_REMOTE_MODULE_EVIDENCE_HASH", "remote module acquisition evidence hash mismatch")
    return {**payload, "evidence_hash": raw["evidence_hash"]}


def _validate_transport_descriptor(descriptor: Any) -> None:
    if not isinstance(descriptor, RemoteModuleTransportDescriptorV2):
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "remote module transport descriptor has wrong type")
    payload = {
        "schema": descriptor.schema,
        "provider_id": descriptor.provider_id,
        "provider_version": descriptor.provider_version,
        "transport_policy": descriptor.transport_policy,
        "maximum_response_bytes": descriptor.maximum_response_bytes,
        "implementation_hash": descriptor.implementation_hash,
    }
    if descriptor.schema != "TEV_SCRIPT_REMOTE_MODULE_TRANSPORT_DESCRIPTOR_V2_R1" or descriptor.transport_policy != REMOTE_MODULE_TRANSPORT_POLICY_V2:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "unsupported remote module transport descriptor schema/policy")
    if not isinstance(descriptor.provider_id, str) or _PROVIDER_ID.fullmatch(descriptor.provider_id) is None or not isinstance(descriptor.provider_version, str) or not descriptor.provider_version:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "invalid remote module transport provider identity")
    _sha(descriptor.implementation_hash, "remote_module_provider.implementation_hash")
    if not isinstance(descriptor.maximum_response_bytes, int) or isinstance(descriptor.maximum_response_bytes, bool) or not 1 <= descriptor.maximum_response_bytes <= MAX_MODULE_SOURCE_BYTES_V2:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "invalid remote module transport response budget")
    if descriptor.descriptor_hash != _hash(payload):
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER_HASH", "remote module transport descriptor hash mismatch")


def _validate_transport_descriptor_wire(raw: Mapping[str, Any]) -> dict[str, Any]:
    fields = {"schema", "provider_id", "provider_version", "transport_policy", "maximum_response_bytes", "implementation_hash", "descriptor_hash"}
    if not isinstance(raw, Mapping) or set(raw) != fields:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", "remote module transport descriptor wire field set mismatch")
    descriptor = RemoteModuleTransportDescriptorV2(
        raw["schema"], raw["provider_id"], raw["provider_version"], raw["transport_policy"],
        raw["maximum_response_bytes"], raw["implementation_hash"], raw["descriptor_hash"]
    )
    _validate_transport_descriptor(descriptor)
    return remote_module_transport_descriptor_to_dict_v2(descriptor)


def _implementation_hash() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError as error:
        _fail("TEVS_V2_REMOTE_MODULE_PROVIDER", f"remote module provider implementation bytes are unreadable: {error}")


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_V2_REMOTE_MODULE_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
