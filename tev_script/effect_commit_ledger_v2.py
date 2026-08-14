from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any, Mapping

from .diagnostics import TevScriptError
from .ir_v4_effect_commands import (
    EffectCommandBatchCommitReceiptV4,
    effect_command_commit_receipt_to_dict_v4,
    load_effect_command_commit_receipt_v4,
)
from .json_io import load_strict_json

LEDGER_SCHEMA_V4 = "TEV_SCRIPT_EFFECT_COMMIT_LEDGER_V4_V1"
LEDGER_CONTENT_SCHEMA_V4 = "TEV_SCRIPT_EFFECT_COMMIT_LEDGER_CONTENT_V4_V1"


class JsonEffectCommitLedgerV4:
    """Durable content-addressed replay ledger for successful R2 batch commits.

    The ledger persists only verified PASS commit receipts. It supplies the same
    lookup/record protocol as EffectCommitLedgerV4, so the R2 commit core can
    suppress provider re-execution after a process restart.
    """

    def __init__(self, path: str | os.PathLike[str]) -> None:
        self.path = Path(path)
        parent = self.path.parent
        if not parent.exists() or not parent.is_dir():
            _fail("TEVS_EFFECT_LEDGER_PARENT", "ledger parent must already exist and be a directory")
        self._receipts: dict[str, EffectCommandBatchCommitReceiptV4] = {}
        if self.path.exists():
            if self.path.is_dir():
                _fail("TEVS_EFFECT_LEDGER_PATH", "ledger path cannot be a directory")
            self._load()

    def lookup(self, batch_hash: str) -> EffectCommandBatchCommitReceiptV4 | None:
        _sha(batch_hash, "batch_hash")
        return self._receipts.get(batch_hash)

    def record(self, receipt: EffectCommandBatchCommitReceiptV4) -> None:
        wire = effect_command_commit_receipt_to_dict_v4(receipt)
        if receipt.status != "PASS":
            _fail("TEVS_EFFECT_LEDGER_STATUS", "durable ledger stores successful PASS commit receipts only")
        existing = self._receipts.get(receipt.batch_hash)
        if existing is not None:
            if existing.receipt_hash != receipt.receipt_hash:
                _fail("TEVS_EFFECT_LEDGER_CONFLICT", "same batch hash cannot map to two commit receipts")
            return
        candidate = dict(self._receipts)
        candidate[receipt.batch_hash] = load_effect_command_commit_receipt_v4(wire)
        payload = _ledger_wire(candidate)
        _atomic_write(self.path, (_canonical_json(payload) + "\n").encode("utf-8"))
        self._receipts = candidate

    @property
    def ledger_hash(self) -> str:
        return _ledger_wire(self._receipts)["ledger_hash"]

    @property
    def entry_count(self) -> int:
        return len(self._receipts)

    def snapshot(self) -> dict[str, Any]:
        return _ledger_wire(self._receipts)

    def _load(self) -> None:
        try:
            raw = load_strict_json(self.path)
        except (OSError, UnicodeError, ValueError) as error:
            _fail("TEVS_EFFECT_LEDGER_READ", f"ledger cannot be read as strict JSON: {error}")
        item = _object(raw, "ledger")
        _exact(item, {"schema", "entries", "ledger_hash"}, "ledger")
        if item["schema"] != LEDGER_SCHEMA_V4:
            _fail("TEVS_EFFECT_LEDGER_SCHEMA", f"unsupported ledger schema {item['schema']!r}")
        entries = item["entries"]
        if not isinstance(entries, list):
            _fail("TEVS_EFFECT_LEDGER_SHAPE", "ledger entries must be an array")
        receipts: dict[str, EffectCommandBatchCommitReceiptV4] = {}
        previous: str | None = None
        for index, raw_entry in enumerate(entries):
            entry = _object(raw_entry, f"ledger.entries[{index}]")
            _exact(entry, {"batch_hash", "receipt"}, f"ledger.entries[{index}]")
            batch_hash = _sha(entry["batch_hash"], f"ledger.entries[{index}].batch_hash")
            if previous is not None and batch_hash <= previous:
                _fail("TEVS_EFFECT_LEDGER_ORDER", "ledger entries must be strictly sorted by batch hash")
            previous = batch_hash
            receipt = load_effect_command_commit_receipt_v4(_object(entry["receipt"], f"ledger.entries[{index}].receipt"))
            if receipt.status != "PASS":
                _fail("TEVS_EFFECT_LEDGER_STATUS", "durable ledger cannot contain failed commit receipts")
            if receipt.batch_hash != batch_hash:
                _fail("TEVS_EFFECT_LEDGER_BATCH", "ledger entry batch hash differs from receipt")
            receipts[batch_hash] = receipt
        expected = _ledger_wire(receipts)
        declared_hash = _sha(item["ledger_hash"], "ledger.ledger_hash")
        if declared_hash != expected["ledger_hash"]:
            _fail("TEVS_EFFECT_LEDGER_HASH", "ledger hash mismatch")
        if item["entries"] != expected["entries"]:
            _fail("TEVS_EFFECT_LEDGER_CANONICAL", "ledger entries are not canonical")
        self._receipts = receipts


def _ledger_wire(receipts: Mapping[str, EffectCommandBatchCommitReceiptV4]) -> dict[str, Any]:
    entries = []
    for batch_hash in sorted(receipts):
        receipt = receipts[batch_hash]
        wire = effect_command_commit_receipt_to_dict_v4(receipt)
        if receipt.status != "PASS":
            _fail("TEVS_EFFECT_LEDGER_STATUS", "durable ledger stores PASS receipts only")
        if receipt.batch_hash != batch_hash:
            _fail("TEVS_EFFECT_LEDGER_BATCH", "ledger key differs from receipt batch hash")
        entries.append({"batch_hash": batch_hash, "receipt": wire})
    content = {"schema": LEDGER_CONTENT_SCHEMA_V4, "entries": entries}
    return {"schema": LEDGER_SCHEMA_V4, "entries": entries, "ledger_hash": _hash(content)}


def _atomic_write(path: Path, data: bytes) -> None:
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any, path: str) -> str:
    if not isinstance(value, str) or len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        _fail("TEVS_EFFECT_LEDGER_HASH_VALUE", f"{path} must be lowercase sha256 hex")
    return value


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        _fail("TEVS_EFFECT_LEDGER_SHAPE", f"{path} must be an object")
    return dict(value)


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        _fail("TEVS_EFFECT_LEDGER_SHAPE", f"{path} field set mismatch: {sorted(set(value) ^ expected)}")


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
