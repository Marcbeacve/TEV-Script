from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .remote_module_acquisition_v2 import (
    RemoteModuleTransportV2,
    acquire_remote_module_bundle_v2,
    validate_remote_module_acquisition_result_v2,
    validate_remote_module_manifest_v2,
)

SIGNATURE_ALGORITHM_V2 = "ed25519"
_KEY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")


def ed25519_public_key_sha256_v2(public_key_raw: bytes) -> str:
    if not isinstance(public_key_raw, bytes) or len(public_key_raw) != 32:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY", "Ed25519 public key must be exactly 32 raw bytes")
    return hashlib.sha256(public_key_raw).hexdigest()


def sign_remote_module_manifest_ed25519_v2(
    manifest_raw: Mapping[str, Any],
    private_key_raw: bytes,
    *,
    key_id: str,
) -> dict[str, Any]:
    manifest = validate_remote_module_manifest_v2(manifest_raw)
    if not isinstance(private_key_raw, bytes) or len(private_key_raw) != 32:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY", "Ed25519 private key seed must be exactly 32 raw bytes")
    key_id = _validate_key_id(key_id)
    Ed25519PrivateKey, _Ed25519PublicKey, Encoding, PublicFormat, _InvalidSignature, _version = _cryptography_api()
    try:
        private_key = Ed25519PrivateKey.from_private_bytes(private_key_raw)
        public_key_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        message = _signature_message(manifest)
        signature = private_key.sign(message)
    except (TypeError, ValueError) as error:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY", f"invalid Ed25519 private key: {error}")
    public_key_sha = ed25519_public_key_sha256_v2(public_key_raw)
    signature_sha = hashlib.sha256(signature).hexdigest()
    payload = {
        "schema": "TEV_SCRIPT_SIGNED_REMOTE_MODULE_MANIFEST_V2_R1",
        "algorithm": SIGNATURE_ALGORITHM_V2,
        "key_id": key_id,
        "public_key_raw_b64": _b64(public_key_raw),
        "public_key_sha256": public_key_sha,
        "manifest": manifest,
        "manifest_hash": manifest["manifest_hash"],
        "signature_b64": _b64(signature),
        "signature_sha256": signature_sha,
    }
    return {**payload, "envelope_hash": _hash(payload)}


def verify_signed_remote_module_manifest_v2(
    raw: Mapping[str, Any],
    *,
    expected_public_key_sha256: str,
) -> dict[str, Any]:
    envelope = _validate_signed_envelope_shape(raw)
    expected_key = _sha(expected_public_key_sha256, "expected_public_key_sha256")
    if envelope["public_key_sha256"] != expected_key:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_TRUST", "signed remote module manifest public key pin mismatch")
    public_key_raw = _decode_b64_exact(envelope["public_key_raw_b64"], expected_length=32, path="public_key_raw_b64")
    if ed25519_public_key_sha256_v2(public_key_raw) != envelope["public_key_sha256"]:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY", "embedded public key bytes do not match public_key_sha256")
    signature = _decode_b64_exact(envelope["signature_b64"], expected_length=64, path="signature_b64")
    if hashlib.sha256(signature).hexdigest() != envelope["signature_sha256"]:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_HASH", "Ed25519 signature bytes do not match signature_sha256")
    _Ed25519PrivateKey, Ed25519PublicKey, _Encoding, _PublicFormat, InvalidSignature, crypto_version = _cryptography_api()
    try:
        Ed25519PublicKey.from_public_bytes(public_key_raw).verify(signature, _signature_message(envelope["manifest"]))
    except InvalidSignature:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_INVALID", "Ed25519 signature verification failed")
    except (TypeError, ValueError) as error:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY", f"invalid Ed25519 public key: {error}")
    verifier_hash = _implementation_hash()
    receipt_payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_MANIFEST_VERIFICATION_RECEIPT_V2_R1",
        "algorithm": SIGNATURE_ALGORITHM_V2,
        "key_id": envelope["key_id"],
        "public_key_sha256": envelope["public_key_sha256"],
        "manifest_hash": envelope["manifest_hash"],
        "signature_sha256": envelope["signature_sha256"],
        "envelope_hash": envelope["envelope_hash"],
        "verifier": "cryptography.ed25519",
        "verifier_version": crypto_version,
        "verifier_implementation_hash": verifier_hash,
    }
    verification = {**receipt_payload, "verification_hash": _hash(receipt_payload)}
    return {
        "schema": "TEV_SCRIPT_VERIFIED_REMOTE_MODULE_MANIFEST_V2_R1",
        "manifest": envelope["manifest"],
        "signed_envelope": envelope,
        "verification": verification,
    }


def acquire_signed_remote_module_bundle_v2(
    signed_manifest_raw: Mapping[str, Any],
    *,
    expected_public_key_sha256: str,
    transport: RemoteModuleTransportV2,
) -> dict[str, Any]:
    verified = verify_signed_remote_module_manifest_v2(
        signed_manifest_raw,
        expected_public_key_sha256=expected_public_key_sha256,
    )
    acquisition = acquire_remote_module_bundle_v2(verified["manifest"], transport)
    if acquisition["manifest"]["manifest_hash"] != verified["verification"]["manifest_hash"]:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_BINDING", "acquired manifest hash diverges from verified signed manifest")
    payload = {
        "schema": "TEV_SCRIPT_SIGNED_REMOTE_MODULE_ACQUISITION_RESULT_V2_R1",
        "signed_manifest": verified["signed_envelope"],
        "verification": verified["verification"],
        "acquisition": acquisition,
    }
    return {**payload, "signed_result_hash": _hash(payload)}


def validate_signed_remote_module_acquisition_result_v2(
    raw: Mapping[str, Any],
    *,
    expected_public_key_sha256: str,
    expected_transport_descriptor_hash: str | None = None,
) -> dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != {"schema", "signed_manifest", "verification", "acquisition", "signed_result_hash"}:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNED_RESULT", "signed remote module acquisition result field set mismatch")
    if raw["schema"] != "TEV_SCRIPT_SIGNED_REMOTE_MODULE_ACQUISITION_RESULT_V2_R1":
        _fail("TEVS_V2_REMOTE_MODULE_SIGNED_RESULT", "unsupported signed remote module acquisition result schema")
    verified = verify_signed_remote_module_manifest_v2(
        raw["signed_manifest"],
        expected_public_key_sha256=expected_public_key_sha256,
    )
    if raw["verification"] != verified["verification"]:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_RECEIPT", "stored manifest verification receipt does not recompute exactly")
    acquisition = validate_remote_module_acquisition_result_v2(
        raw["acquisition"],
        expected_transport_descriptor_hash=expected_transport_descriptor_hash,
        expected_manifest_hash=verified["manifest"]["manifest_hash"],
    )
    payload = {
        "schema": raw["schema"],
        "signed_manifest": verified["signed_envelope"],
        "verification": verified["verification"],
        "acquisition": acquisition,
    }
    if raw["signed_result_hash"] != _hash(payload):
        _fail("TEVS_V2_REMOTE_MODULE_SIGNED_RESULT_HASH", "signed remote module acquisition result hash mismatch")
    return {**payload, "signed_result_hash": raw["signed_result_hash"]}


def module_bundle_from_signed_remote_acquisition_v2(
    raw: Mapping[str, Any],
    *,
    expected_public_key_sha256: str,
    expected_transport_descriptor_hash: str | None = None,
) -> dict[str, Any]:
    result = validate_signed_remote_module_acquisition_result_v2(
        raw,
        expected_public_key_sha256=expected_public_key_sha256,
        expected_transport_descriptor_hash=expected_transport_descriptor_hash,
    )
    return result["acquisition"]["bundle"]


def _validate_signed_envelope_shape(raw: Mapping[str, Any]) -> dict[str, Any]:
    fields = {"schema", "algorithm", "key_id", "public_key_raw_b64", "public_key_sha256", "manifest", "manifest_hash", "signature_b64", "signature_sha256", "envelope_hash"}
    if not isinstance(raw, Mapping) or set(raw) != fields:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE", "signed remote module manifest field set mismatch")
    if raw["schema"] != "TEV_SCRIPT_SIGNED_REMOTE_MODULE_MANIFEST_V2_R1" or raw["algorithm"] != SIGNATURE_ALGORITHM_V2:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE", "unsupported signed remote module manifest schema/algorithm")
    manifest = validate_remote_module_manifest_v2(raw["manifest"])
    if raw["manifest_hash"] != manifest["manifest_hash"]:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_BINDING", "signed envelope manifest_hash mismatch")
    key_id = _validate_key_id(raw["key_id"])
    key_sha = _sha(raw["public_key_sha256"], "signed_manifest.public_key_sha256")
    sig_sha = _sha(raw["signature_sha256"], "signed_manifest.signature_sha256")
    if not isinstance(raw["public_key_raw_b64"], str) or not isinstance(raw["signature_b64"], str):
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE", "signed manifest key/signature encodings must be base64 Text")
    payload = {
        "schema": raw["schema"],
        "algorithm": SIGNATURE_ALGORITHM_V2,
        "key_id": key_id,
        "public_key_raw_b64": raw["public_key_raw_b64"],
        "public_key_sha256": key_sha,
        "manifest": manifest,
        "manifest_hash": manifest["manifest_hash"],
        "signature_b64": raw["signature_b64"],
        "signature_sha256": sig_sha,
    }
    if raw["envelope_hash"] != _hash(payload):
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_ENVELOPE_HASH", "signed manifest envelope hash mismatch")
    return {**payload, "envelope_hash": raw["envelope_hash"]}


def _signature_message(manifest: Mapping[str, Any]) -> bytes:
    canonical = validate_remote_module_manifest_v2(manifest)
    payload = {
        "schema": "TEV_SCRIPT_REMOTE_MODULE_MANIFEST_SIGNATURE_PAYLOAD_V2_R1",
        "algorithm": SIGNATURE_ALGORITHM_V2,
        "manifest_hash": canonical["manifest_hash"],
        "manifest": canonical,
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _cryptography_api():
    try:
        import cryptography
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
    except ImportError as error:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_BACKEND", f"Ed25519 verification requires optional cryptography backend: {error}")
    return Ed25519PrivateKey, Ed25519PublicKey, Encoding, PublicFormat, InvalidSignature, cryptography.__version__


def _decode_b64_exact(value: str, *, expected_length: int, path: str) -> bytes:
    if not isinstance(value, str):
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_ENCODING", f"{path} must be base64 Text")
    try:
        decoded = base64.b64decode(value.encode("ascii"), validate=True)
    except (ValueError, UnicodeEncodeError) as error:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_ENCODING", f"{path} is invalid base64: {error}")
    if len(decoded) != expected_length or _b64(decoded) != value:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_ENCODING", f"{path} must be canonical base64 of {expected_length} bytes")
    return decoded


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _validate_key_id(value: Any) -> str:
    if not isinstance(value, str) or _KEY_ID.fullmatch(value) is None:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_KEY_ID", "signed manifest key_id is invalid")
    return value


def _implementation_hash() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError as error:
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_BACKEND", f"signature verifier implementation bytes are unreadable: {error}")


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_V2_REMOTE_MODULE_SIGNATURE_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
