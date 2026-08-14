from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .diagnostics import TevScriptError
from .ir_v4_effect_commands import (
    EffectAuthorityGrantV4,
    EffectCommandBatchV4,
    EffectProviderDescriptorV4,
    ProviderBatchObservationV4,
    build_effect_command_table_v4,
    build_effect_provider_descriptor_v4,
    build_provider_batch_observation_v4,
)
from .ir_v4_values import TypeTableV4
from .scoped_filesystem_v2 import (
    ScopedFilesystemRootV2,
    open_scoped_root_v2,
    replace_scoped_file_v2,
)
from . import scoped_filesystem_v2 as _scoped_filesystem

FILE_REPLACE_COMMAND_ID_V2 = "file.replace"
FILE_PROVIDER_ID_V2 = "tev.file_replace"
FILE_PROVIDER_VERSION_V2 = "1.0.0"


@dataclass(frozen=True, slots=True)
class FileEffectScopeV2:
    root: str
    scope_hash: str


@dataclass(frozen=True, slots=True)
class FileReplaceEffectReceiptV2:
    schema: str
    intent_hash: str
    command_id: str
    authority_scope_hash: str
    relative_path: str
    data_sha256: str
    byte_count: int
    final_sha256: str
    receipt_hash: str


def build_file_effect_scope_v2(root: str | os.PathLike[str]) -> FileEffectScopeV2:
    try:
        with open_scoped_root_v2(root) as filesystem:
            return FileEffectScopeV2(filesystem.canonical_root, filesystem.scope_hash)
    except TevScriptError as error:
        _raise_scoped_provider_error(error)


def build_file_replace_command_table_v4(table: TypeTableV4):
    return build_effect_command_table_v4([
        {
            "command_id": FILE_REPLACE_COMMAND_ID_V2,
            "parameters": ["Text", "Text"],
            "kind": "effect_command",
            "idempotency_policy": "content_addressed_v1",
        }
    ], table)


class AtomicFileReplaceProviderV2:
    """Single-intent, root-scoped atomic file replacement provider.

    R2 deliberately limits one batch to one file.replace intent. This lets the
    provider truthfully advertise atomic_batch_v1 using same-directory
    temp-write + fsync + os.replace. Multi-file atomicity remains unsupported.
    """

    def __init__(
        self,
        root: str | os.PathLike[str],
        *,
        contract_hash: str,
        provider_implementation_hash: str | None = None,
    ) -> None:
        try:
            self._filesystem: ScopedFilesystemRootV2 = open_scoped_root_v2(root)
        except TevScriptError as error:
            _raise_scoped_provider_error(error)
        self.scope = FileEffectScopeV2(
            self._filesystem.canonical_root,
            self._filesystem.scope_hash,
        )
        try:
            self.contract_hash = _sha(contract_hash, "contract_hash")
            implementation_hash = provider_implementation_hash or _implementation_hash()
            self._descriptor = build_effect_provider_descriptor_v4(
                provider_id=FILE_PROVIDER_ID_V2,
                provider_version=FILE_PROVIDER_VERSION_V2,
                provider_implementation_hash=implementation_hash,
                supported_contract_hashes=[self.contract_hash],
                commit_semantics="atomic_batch_v1",
            )
        except Exception:
            self._filesystem.close()
            raise
        self._effect_receipts: dict[str, FileReplaceEffectReceiptV2] = {}
        self.commit_calls = 0
        self.physical_replace_calls = 0

    def __enter__(self) -> "AtomicFileReplaceProviderV2":
        self._filesystem._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        self._filesystem.close()

    @property
    def descriptor(self) -> EffectProviderDescriptorV4:
        return self._descriptor

    @property
    def effect_receipts(self) -> tuple[FileReplaceEffectReceiptV2, ...]:
        return tuple(self._effect_receipts[key] for key in sorted(self._effect_receipts))

    def commit_batch(
        self,
        batch: EffectCommandBatchV4,
        authority: EffectAuthorityGrantV4,
    ) -> ProviderBatchObservationV4:
        self.commit_calls += 1
        if authority.authority_scope_hash != self.scope.scope_hash:
            _fail("TEVS_FILE_PROVIDER_SCOPE_AUTHORITY", "authority grant is bound to a different filesystem root")
        if authority.provider_descriptor_hash != self.descriptor.descriptor_hash:
            _fail("TEVS_FILE_PROVIDER_DESCRIPTOR", "authority grant is bound to a different provider descriptor")
        if authority.batch_hash != batch.batch_hash:
            _fail("TEVS_FILE_PROVIDER_BATCH", "authority grant is bound to a different batch")
        if len(batch.intents) != 1:
            return build_provider_batch_observation_v4(
                batch_hash=batch.batch_hash,
                provider_descriptor_hash=self.descriptor.descriptor_hash,
                authority_grant_hash=authority.grant_hash,
                status="FAIL",
                intent_receipts=[],
                provider_batch_receipt_hash=_hash({
                    "schema": "TEV_SCRIPT_FILE_PROVIDER_BATCH_FAIL_V2_V1",
                    "batch_hash": batch.batch_hash,
                    "reason": "SINGLE_INTENT_ONLY",
                }),
            )
        intent = batch.intents[0]
        if intent.command_id != FILE_REPLACE_COMMAND_ID_V2:
            _fail("TEVS_FILE_PROVIDER_COMMAND", f"unsupported command {intent.command_id!r}")
        if intent.contract_hash != self.contract_hash:
            _fail("TEVS_FILE_PROVIDER_CONTRACT", "file.replace intent contract hash mismatch")
        if len(intent.argument_encodings) != 2:
            _fail("TEVS_FILE_PROVIDER_ARGUMENTS", "file.replace requires path and data Text arguments")
        relative_path, data = intent.argument_encodings
        if not isinstance(relative_path, str) or not isinstance(data, str):
            _fail("TEVS_FILE_PROVIDER_ARGUMENTS", "file.replace wire arguments must be canonical Text strings")

        data_bytes = data.encode("utf-8")
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        try:
            replacement = replace_scoped_file_v2(self._filesystem, relative_path, data_bytes)
            if replacement.replaced:
                self.physical_replace_calls += 1
        except TevScriptError as error:
            _raise_scoped_provider_error(error)
        relative_canonical = replacement.canonical_relative_path
        final_hash = replacement.content_sha256
        if final_hash != data_hash or replacement.byte_count != len(data_bytes):
            _fail("TEVS_FILE_PROVIDER_VERIFY", "post-replace content does not match requested bytes")

        payload = {
            "schema": "TEV_SCRIPT_FILE_REPLACE_EFFECT_RECEIPT_V2_V1",
            "intent_hash": intent.intent_hash,
            "command_id": intent.command_id,
            "authority_scope_hash": self.scope.scope_hash,
            "relative_path": relative_canonical,
            "data_sha256": data_hash,
            "byte_count": len(data_bytes),
            "final_sha256": final_hash,
        }
        receipt = FileReplaceEffectReceiptV2(
            payload["schema"],
            intent.intent_hash,
            intent.command_id,
            self.scope.scope_hash,
            relative_canonical,
            data_hash,
            len(data_bytes),
            final_hash,
            _hash(payload),
        )
        self._effect_receipts[receipt.receipt_hash] = receipt
        provider_batch_hash = _hash({
            "schema": "TEV_SCRIPT_FILE_PROVIDER_BATCH_RECEIPT_V2_V1",
            "batch_hash": batch.batch_hash,
            "provider_descriptor_hash": self.descriptor.descriptor_hash,
            "authority_scope_hash": self.scope.scope_hash,
            "intent_receipts": [{"intent_hash": intent.intent_hash, "effect_receipt_hash": receipt.receipt_hash}],
        })
        return build_provider_batch_observation_v4(
            batch_hash=batch.batch_hash,
            provider_descriptor_hash=self.descriptor.descriptor_hash,
            authority_grant_hash=authority.grant_hash,
            status="PASS",
            intent_receipts=[(intent.intent_hash, receipt.receipt_hash)],
            provider_batch_receipt_hash=provider_batch_hash,
        )

def file_effect_receipt_to_dict_v2(receipt: FileReplaceEffectReceiptV2) -> dict[str, Any]:
    if not isinstance(receipt, FileReplaceEffectReceiptV2):
        _fail("TEVS_FILE_PROVIDER_RECEIPT", "expected FileReplaceEffectReceiptV2")
    payload = {
        "schema": receipt.schema,
        "intent_hash": receipt.intent_hash,
        "command_id": receipt.command_id,
        "authority_scope_hash": receipt.authority_scope_hash,
        "relative_path": receipt.relative_path,
        "data_sha256": receipt.data_sha256,
        "byte_count": receipt.byte_count,
        "final_sha256": receipt.final_sha256,
    }
    if receipt.receipt_hash != _hash(payload):
        _fail("TEVS_FILE_PROVIDER_RECEIPT_HASH", "file effect receipt hash mismatch")
    return {**payload, "receipt_hash": receipt.receipt_hash}



def _implementation_hash() -> str:
    try:
        payload = {
            "schema": "TEV_SCRIPT_FILE_PROVIDER_IMPLEMENTATION_V2_V1",
            "provider_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "scoped_filesystem_sha256": hashlib.sha256(Path(_scoped_filesystem.__file__).read_bytes()).hexdigest(),
        }
        return _hash(payload)
    except OSError as error:
        _fail("TEVS_FILE_PROVIDER_IMPLEMENTATION", f"provider implementation bytes are unreadable: {error}")


def _raise_scoped_provider_error(error: TevScriptError) -> None:
    code = error.diagnostic.code
    if code == "TEVS_SCOPED_FS_ESCAPE":
        _fail("TEVS_FILE_PROVIDER_PATH_ESCAPE", error.diagnostic.message)
    if code in {"TEVS_SCOPED_FS_PATH", "TEVS_SCOPED_FS_KIND", "TEVS_SCOPED_FS_ROOT"}:
        _fail("TEVS_FILE_PROVIDER_PATH", error.diagnostic.message)
    if code == "TEVS_SCOPED_FS_VERIFY":
        _fail("TEVS_FILE_PROVIDER_VERIFY", error.diagnostic.message)
    _fail("TEVS_FILE_PROVIDER_IO", error.diagnostic.message)


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_FILE_PROVIDER_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
