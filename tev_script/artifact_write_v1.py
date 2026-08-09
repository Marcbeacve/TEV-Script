from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import tempfile

from .diagnostics import TevScriptError


@dataclass(frozen=True, slots=True)
class ArtifactOutputV1:
    path: Path
    content: str


@dataclass(frozen=True, slots=True)
class ArtifactTransactionResultV1:
    ir_path: Path
    receipt_path: Path | None


def write_compilation_artifacts_v1(
    ir_path: str | Path,
    ir_content: str,
    *,
    receipt_path: str | Path | None = None,
    receipt_content: str | None = None,
) -> ArtifactTransactionResultV1:
    """Commit IR and optional lowering receipt with evidence-safe ordering.

    Normal exceptions are rolled back. For abrupt process/power failure the
    ordering intentionally prefers a missing receipt over a stale receipt that
    appears to attest to newly replaced IR bytes:

      1. fully stage and fsync all new bytes;
      2. move any old receipt away from its authoritative path;
      3. atomically replace IR;
      4. atomically install the new receipt last.

    This cannot make two independent filesystem paths one hardware-atomic
    transaction. It does ensure that receipt presence is the final commit
    witness, and it restores previous files on ordinary exceptions.
    """

    if (receipt_path is None) != (receipt_content is None):
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_RECEIPT_PAIR",
            "receipt path and content must either both be supplied or both be absent",
        )

    ir = _prepare_destination(ir_path, "IR")
    receipt = (
        _prepare_destination(receipt_path, "receipt")
        if receipt_path is not None
        else None
    )
    if receipt is not None and _same_destination(ir, receipt):
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_PATH_COLLISION",
            "IR and lowering receipt must use different output paths",
        )

    staged_ir = _stage_text(ir, ir_content)
    staged_receipt = _stage_text(receipt, receipt_content) if receipt is not None else None
    ir_backup: Path | None = None
    receipt_backup: Path | None = None
    ir_committed = False
    receipt_committed = False

    try:
        # Preserve old IR for rollback without removing the authoritative file.
        if ir.exists():
            ir_backup = _copy_backup(ir)

        # A stale receipt must never remain authoritative while IR changes.
        if receipt is not None and receipt.exists():
            receipt_backup = _reserve_backup_path(receipt)
            os.replace(receipt, receipt_backup)
            _fsync_directory(receipt.parent)

        os.replace(staged_ir, ir)
        staged_ir = None
        ir_committed = True
        _fsync_directory(ir.parent)

        if receipt is not None:
            assert staged_receipt is not None
            os.replace(staged_receipt, receipt)
            staged_receipt = None
            receipt_committed = True
            _fsync_directory(receipt.parent)

        _safe_unlink(ir_backup)
        _safe_unlink(receipt_backup)
        return ArtifactTransactionResultV1(ir, receipt)
    except Exception as error:
        rollback_error: Exception | None = None
        try:
            if receipt is not None and receipt_committed:
                _safe_unlink(receipt)
            if receipt is not None and receipt_backup is not None and receipt_backup.exists():
                os.replace(receipt_backup, receipt)
                receipt_backup = None
                _fsync_directory(receipt.parent)

            if ir_committed:
                if ir_backup is not None and ir_backup.exists():
                    os.replace(ir_backup, ir)
                    ir_backup = None
                else:
                    _safe_unlink(ir)
                _fsync_directory(ir.parent)
        except Exception as rollback:
            rollback_error = rollback
        finally:
            _safe_unlink(staged_ir)
            _safe_unlink(staged_receipt)
            _safe_unlink(ir_backup)
            _safe_unlink(receipt_backup)

        if rollback_error is not None:
            raise TevScriptError(
                "TEVS_V1_ARTIFACT_ROLLBACK",
                "artifact commit failed and rollback also failed: "
                f"commit={type(error).__name__}; rollback={type(rollback_error).__name__}",
            ) from rollback_error
        if isinstance(error, TevScriptError):
            raise
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_COMMIT",
            f"artifact commit failed closed: {type(error).__name__}",
        ) from error
    finally:
        _safe_unlink(staged_ir)
        _safe_unlink(staged_receipt)
        _safe_unlink(ir_backup)
        _safe_unlink(receipt_backup)


def write_text_artifact_v1(path: str | Path, content: str) -> Path:
    destination = _prepare_destination(path, "artifact")
    staged = _stage_text(destination, content)
    try:
        os.replace(staged, destination)
        staged = None
        _fsync_directory(destination.parent)
        return destination
    except Exception as error:
        if isinstance(error, TevScriptError):
            raise
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_COMMIT",
            f"artifact commit failed closed: {type(error).__name__}",
        ) from error
    finally:
        _safe_unlink(staged)


def _prepare_destination(path: str | Path | None, label: str) -> Path:
    if path is None:
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_PATH",
            f"{label} output path is required",
        )
    destination = Path(path).expanduser()
    if destination.name in {"", ".", ".."}:
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_PATH",
            f"{label} output path must name a file",
        )
    parent = destination.parent if destination.parent != Path("") else Path(".")
    try:
        parent = parent.resolve(strict=True)
    except OSError as exc:
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_PARENT",
            f"{label} output parent does not exist: {parent}",
        ) from exc
    destination = parent / destination.name
    if destination.exists() and destination.is_dir():
        raise TevScriptError(
            "TEVS_V1_ARTIFACT_PATH",
            f"{label} output path is a directory: {destination}",
        )
    return destination


def _same_destination(left: Path, right: Path) -> bool:
    return os.path.normcase(str(left.absolute())) == os.path.normcase(str(right.absolute()))


def _normalized_bytes(content: str) -> bytes:
    return (content.rstrip("\n") + "\n").encode("utf-8")


def _stage_text(destination: Path | None, content: str | None) -> Path | None:
    if destination is None:
        return None
    assert content is not None
    prefix = "." + destination.name + ".tev-stage-"
    descriptor, temporary = tempfile.mkstemp(prefix=prefix, dir=destination.parent)
    path = Path(temporary)
    try:
        data = _normalized_bytes(content)
        with os.fdopen(descriptor, "wb", closefd=True) as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        return path
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        _safe_unlink(path)
        raise


def _reserve_backup_path(destination: Path) -> Path:
    descriptor, temporary = tempfile.mkstemp(
        prefix="." + destination.name + ".tev-backup-",
        dir=destination.parent,
    )
    os.close(descriptor)
    path = Path(temporary)
    path.unlink()
    return path


def _copy_backup(destination: Path) -> Path:
    backup = _reserve_backup_path(destination)
    try:
        shutil.copyfile(destination, backup)
        # Windows requires a writable file descriptor for fsync. Opening the
        # completed copy in update mode preserves its bytes while keeping this
        # durability step portable.
        with backup.open("rb+") as stream:
            os.fsync(stream.fileno())
        return backup
    except Exception:
        _safe_unlink(backup)
        raise


def _safe_unlink(path: Path | None) -> None:
    if path is None:
        return
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


def _fsync_directory(directory: Path) -> None:
    # POSIX can persist rename metadata by fsyncing the containing directory.
    # Windows does not expose the same portable Python operation; os.replace
    # still supplies the same-directory atomic rename primitive there.
    if os.name == "nt":
        return
    flags = getattr(os, "O_DIRECTORY", 0) | os.O_RDONLY
    try:
        descriptor = os.open(directory, flags)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
