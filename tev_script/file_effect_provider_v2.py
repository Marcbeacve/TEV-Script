from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile
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
    raw = os.fspath(root)
    if not isinstance(raw, str) or not raw:
        _fail("TEVS_FILE_PROVIDER_SCOPE", "authorized root must be a non-empty path")
    absolute = os.path.abspath(os.path.normpath(raw))
    try:
        info = os.lstat(absolute)
    except OSError as error:
        _fail("TEVS_FILE_PROVIDER_SCOPE", f"authorized root is not accessible: {error}")
    if _is_link_or_reparse(info):
        _fail("TEVS_FILE_PROVIDER_SCOPE", "authorized root cannot be a symlink or reparse point")
    if not stat.S_ISDIR(info.st_mode):
        _fail("TEVS_FILE_PROVIDER_SCOPE", "authorized root must be an existing directory")
    canonical = _canonical_host_path(absolute)
    payload = {"schema": "TEV_SCRIPT_FILE_EFFECT_SCOPE_V2_V1", "root": canonical}
    return FileEffectScopeV2(canonical, _hash(payload))


def resolve_scoped_file_path_v2(
    root: str | os.PathLike[str],
    raw_relative: str,
    *,
    require_existing: bool,
) -> tuple[Path, str, FileEffectScopeV2]:
    scope = build_file_effect_scope_v2(root)
    if raw_relative == "" or "\x00" in raw_relative:
        _fail("TEVS_FILE_PROVIDER_PATH", "scoped file path must be non-empty and contain no NUL")
    relative = Path(raw_relative)
    if relative.is_absolute() or relative.drive:
        _fail("TEVS_FILE_PROVIDER_PATH", "scoped file path must be relative to the authorized root")
    parts = relative.parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        _fail("TEVS_FILE_PROVIDER_PATH", "scoped file path cannot contain empty, '.', or '..' segments")
    for part in parts:
        _validate_windows_path_segment(part)

    current = Path(os.path.abspath(os.path.normpath(os.fspath(root))))
    for part in parts[:-1]:
        current = current / part
        try:
            info = os.lstat(current)
        except OSError as error:
            _fail("TEVS_FILE_PROVIDER_PATH", f"target parent must already exist: {error}")
        if _is_link_or_reparse(info):
            _fail("TEVS_FILE_PROVIDER_PATH_ESCAPE", "target parent cannot traverse a symlink or reparse point")
        if not stat.S_ISDIR(info.st_mode):
            _fail("TEVS_FILE_PROVIDER_PATH", "target parent component must be a directory")

    parent = current
    target = parent / parts[-1]
    try:
        parent_info = os.lstat(parent)
    except OSError as error:
        _fail("TEVS_FILE_PROVIDER_PATH", f"target parent must already exist: {error}")
    if _is_link_or_reparse(parent_info):
        _fail("TEVS_FILE_PROVIDER_PATH_ESCAPE", "target parent cannot be a symlink or reparse point")
    if not stat.S_ISDIR(parent_info.st_mode):
        _fail("TEVS_FILE_PROVIDER_PATH", "target parent must be a directory")

    try:
        target_info = os.lstat(target)
    except FileNotFoundError:
        target_info = None
    except OSError as error:
        _fail("TEVS_FILE_PROVIDER_PATH", f"existing target cannot be inspected: {error}")
    if target_info is None:
        if require_existing:
            _fail("TEVS_FILE_PROVIDER_PATH", "scoped file target must already exist")
    else:
        if _is_link_or_reparse(target_info):
            _fail("TEVS_FILE_PROVIDER_PATH_ESCAPE", "symlink/reparse targets are not allowed")
        if stat.S_ISDIR(target_info.st_mode):
            _fail("TEVS_FILE_PROVIDER_PATH", "scoped file target cannot be a directory")
        if not stat.S_ISREG(target_info.st_mode):
            _fail("TEVS_FILE_PROVIDER_PATH", "scoped file target must be a regular file")

    return target, "/".join(parts), scope


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
        self.scope = build_file_effect_scope_v2(root)
        self._root = Path(self.scope.root)
        self.contract_hash = _sha(contract_hash, "contract_hash")
        implementation_hash = provider_implementation_hash or _implementation_hash()
        self._descriptor = build_effect_provider_descriptor_v4(
            provider_id=FILE_PROVIDER_ID_V2,
            provider_version=FILE_PROVIDER_VERSION_V2,
            provider_implementation_hash=implementation_hash,
            supported_contract_hashes=[self.contract_hash],
            commit_semantics="atomic_batch_v1",
        )
        self._effect_receipts: dict[str, FileReplaceEffectReceiptV2] = {}
        self.commit_calls = 0
        self.physical_replace_calls = 0

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

        target, relative_canonical = self._resolve_target(relative_path)
        data_bytes = data.encode("utf-8")
        data_hash = hashlib.sha256(data_bytes).hexdigest()
        temporary: str | None = None
        try:
            try:
                current_bytes = target.read_bytes()
            except FileNotFoundError:
                current_bytes = None
            if current_bytes == data_bytes:
                final_bytes = current_bytes
            else:
                fd, temporary = tempfile.mkstemp(prefix=f".{target.name}.tev-r2-", suffix=".tmp", dir=str(target.parent))
                with os.fdopen(fd, "wb") as stream:
                    stream.write(data_bytes)
                    stream.flush()
                    os.fsync(stream.fileno())
                self.physical_replace_calls += 1
                os.replace(temporary, target)
                temporary = None
                final_bytes = target.read_bytes()
        except OSError as error:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass
            _fail("TEVS_FILE_PROVIDER_IO", f"atomic file replacement failed: {error}")
        final_hash = hashlib.sha256(final_bytes).hexdigest()
        if final_hash != data_hash or final_bytes != data_bytes:
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

    def _resolve_target(self, raw_relative: str) -> tuple[Path, str]:
        target, relative_canonical, _scope = resolve_scoped_file_path_v2(
            self._root, raw_relative, require_existing=False
        )
        return target, relative_canonical


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



def _canonical_host_path(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.path.normpath(os.fspath(path)))).replace("\\", "/")


def _is_link_or_reparse(info: os.stat_result) -> bool:
    if stat.S_ISLNK(info.st_mode):
        return True
    attributes = getattr(info, "st_file_attributes", 0)
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & reparse_flag)


def _validate_windows_path_segment(part: str) -> None:
    if part.rstrip(" .") != part or ":" in part:
        _fail("TEVS_FILE_PROVIDER_PATH", "file.replace path contains a Windows-ambiguous segment")
    stem = part.split(".", 1)[0].upper()
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if stem in reserved:
        _fail("TEVS_FILE_PROVIDER_PATH", "file.replace path contains a reserved Windows device name")


def _implementation_hash() -> str:
    try:
        return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    except OSError as error:
        _fail("TEVS_FILE_PROVIDER_IMPLEMENTATION", f"provider implementation bytes are unreadable: {error}")


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_FILE_PROVIDER_HASH", f"{path} must be lowercase sha256 hex")
    return value


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
