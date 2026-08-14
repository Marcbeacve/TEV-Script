from __future__ import annotations

from contextlib import AbstractContextManager
from dataclasses import dataclass
import errno
import hashlib
import json
import os
from pathlib import Path
import secrets
import stat
from typing import Any, Callable

from .diagnostics import TevScriptError


_WINDOWS_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)
_READ_CHUNK_BYTES = 64 * 1024
_SECURE_BACKEND_AVAILABLE = True


@dataclass(frozen=True, slots=True)
class ScopedFileReadV2:
    canonical_relative_path: str
    data: bytes
    content_sha256: str


@dataclass(frozen=True, slots=True)
class ScopedFileReplaceV2:
    canonical_relative_path: str
    content_sha256: str
    byte_count: int
    replaced: bool


class ScopedFilesystemRootV2(AbstractContextManager["ScopedFilesystemRootV2"]):
    __slots__ = (
        "canonical_root",
        "platform",
        "volume_identity",
        "file_identity",
        "scope_hash",
        "_native",
        "_closed",
    )

    def __init__(
        self,
        *,
        canonical_root: str,
        platform: str,
        volume_identity: str,
        file_identity: str,
        native: int,
    ) -> None:
        self.canonical_root = canonical_root
        self.platform = platform
        self.volume_identity = volume_identity
        self.file_identity = file_identity
        payload = {
            "schema": "TEV_SCRIPT_SCOPED_FILESYSTEM_ROOT_V2_V1",
            "canonical_root": canonical_root,
            "platform": platform,
            "volume_identity": volume_identity,
            "file_identity": file_identity,
        }
        self.scope_hash = _hash(payload)
        self._native = native
        self._closed = False

    def __enter__(self) -> "ScopedFilesystemRootV2":
        self._ensure_open()
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        if os.name == "nt":
            _win_close(self._native)
        else:
            os.close(self._native)

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    def _ensure_open(self) -> None:
        if self._closed:
            _fail("TEVS_SCOPED_FS_CLOSED", "scoped filesystem root is closed")

    def _duplicate_native(self) -> int:
        self._ensure_open()
        if os.name == "nt":
            return _win_duplicate(self._native)
        return os.dup(self._native)


def canonical_host_path_v2(path: str | os.PathLike[str]) -> str:
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw:
        _fail("TEVS_SCOPED_FS_ROOT", "filesystem root must be a non-empty path")
    return os.path.normcase(os.path.abspath(os.path.normpath(raw))).replace("\\", "/")


def open_scoped_root_v2(root: str | os.PathLike[str]) -> ScopedFilesystemRootV2:
    if not _SECURE_BACKEND_AVAILABLE:
        _fail("TEVS_SCOPED_FS_UNSUPPORTED", "secure handle-relative filesystem backend is unavailable")
    canonical = canonical_host_path_v2(root)
    if os.name == "nt":
        handle = _win_open_root(os.fspath(root))
        try:
            info = _win_information(handle)
            _win_require_kind(info, directory=True, path="authorized root")
            final_path = _win_final_path(handle)
            return ScopedFilesystemRootV2(
                canonical_root=_canonical_windows_final_path(final_path),
                platform="windows",
                volume_identity=f"{info.dwVolumeSerialNumber:08x}",
                file_identity=f"{info.nFileIndexHigh:08x}{info.nFileIndexLow:08x}",
                native=handle,
            )
        except Exception:
            _win_close(handle)
            raise

    required_flags = ("O_DIRECTORY", "O_NOFOLLOW", "O_NONBLOCK")
    if any(not hasattr(os, name) for name in required_flags):
        _fail("TEVS_SCOPED_FS_UNSUPPORTED", "POSIX secure directory primitives are unavailable")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(os.fspath(root), flags)
    except OSError as error:
        code = "TEVS_SCOPED_FS_ESCAPE" if error.errno == errno.ELOOP else "TEVS_SCOPED_FS_ROOT"
        _fail(code, f"filesystem root cannot be opened securely: {error}")
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISDIR(info.st_mode):
            _fail("TEVS_SCOPED_FS_ROOT", "filesystem root must be a directory")
        return ScopedFilesystemRootV2(
            canonical_root=canonical,
            platform="posix",
            volume_identity=f"{info.st_dev:x}",
            file_identity=f"{info.st_ino:x}",
            native=descriptor,
        )
    except Exception:
        os.close(descriptor)
        raise


def read_scoped_file_v2(
    root: ScopedFilesystemRootV2,
    raw_relative: str,
    *,
    maximum_bytes: int,
) -> ScopedFileReadV2:
    scope = _require_scope(root)
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int) or maximum_bytes < 0:
        _fail("TEVS_SCOPED_FS_BUDGET", "maximum_bytes must be a non-negative integer")
    parts, canonical = _parse_relative(raw_relative)
    if os.name == "nt":
        parent = _win_open_parent(scope, parts[:-1])
        try:
            try:
                handle = _win_open_relative(
                    parent,
                    parts[-1],
                    desired_access=_WIN_FILE_READ_DATA | _WIN_FILE_READ_ATTRIBUTES | _WIN_SYNCHRONIZE,
                    create_disposition=_WIN_FILE_OPEN,
                    create_options=(
                        _WIN_FILE_NON_DIRECTORY_FILE
                        | _WIN_FILE_OPEN_REPARSE_POINT
                        | _WIN_FILE_SYNCHRONOUS_IO_NONALERT
                    ),
                )
            except FileNotFoundError as error:
                _fail("TEVS_SCOPED_FS_PATH", f"scoped file {canonical!r} does not exist: {error}")
            except OSError as error:
                _fail("TEVS_SCOPED_FS_IO", f"scoped file {canonical!r} cannot be opened securely: {error}")
            try:
                _win_require_kind(_win_information(handle), directory=False, path=canonical)
                data = _consume_bounded_v2(lambda count: _win_read(handle, count), maximum_bytes)
            finally:
                _win_close(handle)
        finally:
            _win_close(parent)
    else:
        parent = _posix_open_parent(scope, parts[:-1])
        try:
            descriptor = _posix_open_file(parent, parts[-1], canonical)
            try:
                data = _consume_bounded_v2(lambda count: os.read(descriptor, count), maximum_bytes)
            finally:
                os.close(descriptor)
        finally:
            os.close(parent)
    return ScopedFileReadV2(canonical, data, hashlib.sha256(data).hexdigest())


def replace_scoped_file_v2(
    root: ScopedFilesystemRootV2,
    raw_relative: str,
    data: bytes,
) -> ScopedFileReplaceV2:
    scope = _require_scope(root)
    if not isinstance(data, bytes):
        _fail("TEVS_SCOPED_FS_DATA", "replacement data must be bytes")
    parts, canonical = _parse_relative(raw_relative)
    digest = hashlib.sha256(data).hexdigest()
    if os.name == "nt":
        replaced = _win_replace(scope, parts, canonical, data)
    else:
        replaced = _posix_replace(scope, parts, canonical, data)
    return ScopedFileReplaceV2(canonical, digest, len(data), replaced)


def _consume_bounded_v2(read_chunk: Callable[[int], bytes], maximum_bytes: int) -> bytes:
    if isinstance(maximum_bytes, bool) or not isinstance(maximum_bytes, int) or maximum_bytes < 0:
        _fail("TEVS_SCOPED_FS_BUDGET", "maximum_bytes must be a non-negative integer")
    admitted = bytearray()
    while True:
        remaining_with_witness = maximum_bytes + 1 - len(admitted)
        if remaining_with_witness <= 0:
            _fail("TEVS_SCOPED_FS_BUDGET", f"file content exceeds {maximum_bytes} bytes")
        requested = min(_READ_CHUNK_BYTES, remaining_with_witness)
        chunk = read_chunk(requested)
        if not isinstance(chunk, bytes):
            _fail("TEVS_SCOPED_FS_IO", "filesystem reader returned non-bytes content")
        if len(chunk) > requested:
            _fail("TEVS_SCOPED_FS_IO", "filesystem reader exceeded its requested bound")
        if not chunk:
            return bytes(admitted)
        admitted.extend(chunk)
        if len(admitted) > maximum_bytes:
            _fail("TEVS_SCOPED_FS_BUDGET", f"file content exceeds {maximum_bytes} bytes")


def _require_scope(root: ScopedFilesystemRootV2) -> ScopedFilesystemRootV2:
    if not isinstance(root, ScopedFilesystemRootV2):
        _fail("TEVS_SCOPED_FS_ROOT", "expected ScopedFilesystemRootV2")
    root._ensure_open()
    expected_platform = "windows" if os.name == "nt" else "posix"
    if root.platform != expected_platform:
        _fail("TEVS_SCOPED_FS_ROOT", "scoped filesystem root belongs to another platform")
    return root


def _parse_relative(raw_relative: str) -> tuple[tuple[str, ...], str]:
    if not isinstance(raw_relative, str) or not raw_relative or "\x00" in raw_relative:
        _fail("TEVS_SCOPED_FS_PATH", "scoped path must be non-empty Text without NUL")
    if raw_relative.startswith(("/", "\\")):
        _fail("TEVS_SCOPED_FS_PATH", "scoped path must be relative")
    normalized = raw_relative.replace("\\", "/")
    parts = normalized.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        _fail("TEVS_SCOPED_FS_PATH", "scoped path contains an empty, '.', or '..' segment")
    for part in parts:
        if part.rstrip(" .") != part or ":" in part:
            _fail("TEVS_SCOPED_FS_PATH", "scoped path contains a Windows-ambiguous segment")
        stem = part.split(".", 1)[0].upper()
        if stem in _WINDOWS_RESERVED:
            _fail("TEVS_SCOPED_FS_PATH", "scoped path contains a reserved Windows device name")
        _validate_win_unicode_name(part)
    return tuple(parts), "/".join(parts)


def _validate_win_unicode_name(name: str) -> int:
    encoded_length = len(name.encode("utf-16-le"))
    if encoded_length + 2 > 0xFFFF:
        _fail("TEVS_SCOPED_FS_PATH", "scoped path segment is too long for Windows")
    return encoded_length


def _posix_open_parent(root: ScopedFilesystemRootV2, parts: tuple[str, ...]) -> int:
    current = root._duplicate_native()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        for part in parts:
            try:
                child = os.open(part, flags, dir_fd=current)
            except OSError as error:
                code = "TEVS_SCOPED_FS_ESCAPE" if error.errno in {errno.ELOOP, errno.ENOTDIR} else "TEVS_SCOPED_FS_PATH"
                _fail(code, f"scoped parent cannot be opened securely: {error}")
            os.close(current)
            current = child
        return current
    except Exception:
        os.close(current)
        raise


def _posix_open_file(parent: int, name: str, canonical: str) -> int:
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent)
    except OSError as error:
        code = "TEVS_SCOPED_FS_ESCAPE" if error.errno == errno.ELOOP else "TEVS_SCOPED_FS_IO"
        _fail(code, f"scoped file {canonical!r} cannot be opened securely: {error}")
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            _fail("TEVS_SCOPED_FS_KIND", "scoped file target must be a regular file")
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _posix_existing_bytes(parent: int, name: str, canonical: str, maximum: int) -> bytes | None:
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | getattr(os, "O_CLOEXEC", 0),
            dir_fd=parent,
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        code = "TEVS_SCOPED_FS_ESCAPE" if error.errno == errno.ELOOP else "TEVS_SCOPED_FS_IO"
        _fail(code, f"existing scoped target {canonical!r} cannot be opened securely: {error}")
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            _fail("TEVS_SCOPED_FS_KIND", "existing scoped target must be a regular file")
        try:
            return _consume_bounded_v2(lambda count: os.read(descriptor, count), maximum)
        except TevScriptError as error:
            if error.diagnostic.code == "TEVS_SCOPED_FS_BUDGET":
                return None
            raise
    finally:
        os.close(descriptor)


def _posix_replace(
    root: ScopedFilesystemRootV2,
    parts: tuple[str, ...],
    canonical: str,
    data: bytes,
) -> bool:
    parent = _posix_open_parent(root, parts[:-1])
    temporary_name: str | None = None
    descriptor: int | None = None
    try:
        if _posix_existing_bytes(parent, parts[-1], canonical, len(data)) == data:
            return False
        for _attempt in range(128):
            candidate = f".{parts[-1]}.tev-v2-{secrets.token_hex(12)}.tmp"
            try:
                descriptor = os.open(
                    candidate,
                    os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0),
                    0o600,
                    dir_fd=parent,
                )
                temporary_name = candidate
                break
            except FileExistsError:
                continue
        if descriptor is None or temporary_name is None:
            _fail("TEVS_SCOPED_FS_IO", "unable to reserve a unique scoped temporary file")
        _posix_write_all(descriptor, data)
        os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        verified = _consume_bounded_v2(lambda count: os.read(descriptor, count), len(data))
        if verified != data:
            _fail("TEVS_SCOPED_FS_VERIFY", "temporary file bytes do not match replacement data")
        try:
            os.replace(temporary_name, parts[-1], src_dir_fd=parent, dst_dir_fd=parent)
        except OSError as error:
            _fail("TEVS_SCOPED_FS_IO", f"scoped atomic replacement failed: {error}")
        temporary_name = None
        os.fsync(parent)
        return True
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent)
            except OSError:
                pass
        os.close(parent)


def _posix_write_all(descriptor: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        try:
            written = os.write(descriptor, data[offset:])
        except OSError as error:
            _fail("TEVS_SCOPED_FS_IO", f"scoped temporary write failed: {error}")
        if written <= 0:
            _fail("TEVS_SCOPED_FS_IO", "scoped temporary write made no progress")
        offset += written


def _hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)


if os.name == "nt":
    import ctypes
    from ctypes import wintypes

    _WIN_FILE_READ_DATA = 0x0001
    _WIN_FILE_WRITE_DATA = 0x0002
    _WIN_FILE_LIST_DIRECTORY = 0x0001
    _WIN_FILE_ADD_FILE = 0x0002
    _WIN_FILE_TRAVERSE = 0x0020
    _WIN_FILE_READ_ATTRIBUTES = 0x0080
    _WIN_DELETE = 0x00010000
    _WIN_SYNCHRONIZE = 0x00100000
    _WIN_FILE_SHARE_READ = 0x00000001
    _WIN_FILE_SHARE_WRITE = 0x00000002
    _WIN_FILE_SHARE_DELETE = 0x00000004
    _WIN_SHARE_ALL = _WIN_FILE_SHARE_READ | _WIN_FILE_SHARE_WRITE | _WIN_FILE_SHARE_DELETE
    _WIN_CREATE_NEW = 1
    _WIN_OPEN_EXISTING = 3
    _WIN_FILE_OPEN = 1
    _WIN_FILE_CREATE = 2
    _WIN_FILE_ATTRIBUTE_NORMAL = 0x00000080
    _WIN_FILE_ATTRIBUTE_DIRECTORY = 0x00000010
    _WIN_FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400
    _WIN_FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
    _WIN_FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
    _WIN_FILE_DIRECTORY_FILE = 0x00000001
    _WIN_FILE_SYNCHRONOUS_IO_NONALERT = 0x00000020
    _WIN_FILE_NON_DIRECTORY_FILE = 0x00000040
    _WIN_FILE_OPEN_FOR_BACKUP_INTENT = 0x00004000
    _WIN_FILE_OPEN_REPARSE_POINT = 0x00200000
    _WIN_OBJ_CASE_INSENSITIVE = 0x00000040
    _WIN_FILE_BEGIN = 0
    _WIN_FILE_RENAME_INFO = 3
    _WIN_FILE_DISPOSITION_INFO = 4
    _WIN_FILE_RENAME_INFORMATION = 10
    _WIN_DUPLICATE_SAME_ACCESS = 0x00000002
    _WIN_INVALID_HANDLE = ctypes.c_void_p(-1).value

    class _WinByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    class _WinUnicodeString(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.USHORT),
            ("MaximumLength", wintypes.USHORT),
            ("Buffer", wintypes.LPWSTR),
        ]

    class _WinObjectAttributes(ctypes.Structure):
        _fields_ = [
            ("Length", wintypes.ULONG),
            ("RootDirectory", wintypes.HANDLE),
            ("ObjectName", ctypes.POINTER(_WinUnicodeString)),
            ("Attributes", wintypes.ULONG),
            ("SecurityDescriptor", wintypes.LPVOID),
            ("SecurityQualityOfService", wintypes.LPVOID),
        ]

    class _WinIoStatusBlockUnion(ctypes.Union):
        _fields_ = [("Status", ctypes.c_long), ("Pointer", wintypes.LPVOID)]

    class _WinIoStatusBlock(ctypes.Structure):
        _anonymous_ = ("u",)
        _fields_ = [("u", _WinIoStatusBlockUnion), ("Information", ctypes.c_size_t)]

    class _WinFileDispositionInformation(ctypes.Structure):
        _fields_ = [("DeleteFile", wintypes.BOOL)]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _ntdll = ctypes.WinDLL("ntdll", use_last_error=True)

    _CreateFileW = _kernel32.CreateFileW
    _CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    _CreateFileW.restype = wintypes.HANDLE

    _CloseHandle = _kernel32.CloseHandle
    _CloseHandle.argtypes = [wintypes.HANDLE]
    _CloseHandle.restype = wintypes.BOOL

    _DuplicateHandle = _kernel32.DuplicateHandle
    _DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    _DuplicateHandle.restype = wintypes.BOOL

    _GetCurrentProcess = _kernel32.GetCurrentProcess
    _GetCurrentProcess.restype = wintypes.HANDLE

    _GetFileInformationByHandle = _kernel32.GetFileInformationByHandle
    _GetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.POINTER(_WinByHandleFileInformation)]
    _GetFileInformationByHandle.restype = wintypes.BOOL

    _GetFinalPathNameByHandleW = _kernel32.GetFinalPathNameByHandleW
    _GetFinalPathNameByHandleW.argtypes = [wintypes.HANDLE, wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD]
    _GetFinalPathNameByHandleW.restype = wintypes.DWORD

    _ReadFile = _kernel32.ReadFile
    _ReadFile.argtypes = [wintypes.HANDLE, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    _ReadFile.restype = wintypes.BOOL

    _WriteFile = _kernel32.WriteFile
    _WriteFile.argtypes = [wintypes.HANDLE, wintypes.LPCVOID, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
    _WriteFile.restype = wintypes.BOOL

    _FlushFileBuffers = _kernel32.FlushFileBuffers
    _FlushFileBuffers.argtypes = [wintypes.HANDLE]
    _FlushFileBuffers.restype = wintypes.BOOL

    _SetFilePointerEx = _kernel32.SetFilePointerEx
    _SetFilePointerEx.argtypes = [wintypes.HANDLE, ctypes.c_longlong, ctypes.POINTER(ctypes.c_longlong), wintypes.DWORD]
    _SetFilePointerEx.restype = wintypes.BOOL

    _SetFileInformationByHandle = _kernel32.SetFileInformationByHandle
    _SetFileInformationByHandle.argtypes = [wintypes.HANDLE, ctypes.c_int, wintypes.LPVOID, wintypes.DWORD]
    _SetFileInformationByHandle.restype = wintypes.BOOL

    _NtCreateFile = _ntdll.NtCreateFile
    _NtCreateFile.argtypes = [
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        ctypes.POINTER(_WinObjectAttributes),
        ctypes.POINTER(_WinIoStatusBlock),
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.ULONG,
    ]
    _NtCreateFile.restype = ctypes.c_long

    _NtSetInformationFile = _ntdll.NtSetInformationFile
    _NtSetInformationFile.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_WinIoStatusBlock),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    _NtSetInformationFile.restype = ctypes.c_long

    _RtlNtStatusToDosError = _ntdll.RtlNtStatusToDosError
    _RtlNtStatusToDosError.argtypes = [ctypes.c_long]
    _RtlNtStatusToDosError.restype = wintypes.ULONG


def _win_open_root(path: str) -> int:
    handle = _CreateFileW(
        path,
        _WIN_FILE_LIST_DIRECTORY | _WIN_FILE_TRAVERSE | _WIN_FILE_READ_ATTRIBUTES | _WIN_SYNCHRONIZE,
        _WIN_SHARE_ALL,
        None,
        _WIN_OPEN_EXISTING,
        _WIN_FILE_FLAG_BACKUP_SEMANTICS | _WIN_FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    value = _handle_value(handle)
    if value == _WIN_INVALID_HANDLE:
        error = ctypes.get_last_error()
        _fail("TEVS_SCOPED_FS_ROOT", f"filesystem root cannot be opened securely: {ctypes.WinError(error)}")
    return value


def _win_duplicate(handle: int) -> int:
    current = _GetCurrentProcess()
    duplicate = wintypes.HANDLE()
    if not _DuplicateHandle(
        current,
        wintypes.HANDLE(handle),
        current,
        ctypes.byref(duplicate),
        0,
        False,
        _WIN_DUPLICATE_SAME_ACCESS,
    ):
        _win_fail("TEVS_SCOPED_FS_IO", "cannot duplicate scoped directory handle")
    return _handle_value(duplicate)


def _win_open_relative(
    parent: int,
    name: str,
    *,
    desired_access: int,
    create_disposition: int,
    create_options: int,
) -> int:
    encoded_length = _validate_win_unicode_name(name)
    name_buffer = ctypes.create_unicode_buffer(name)
    unicode_name = _WinUnicodeString(
        encoded_length,
        encoded_length + 2,
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = _WinObjectAttributes(
        ctypes.sizeof(_WinObjectAttributes),
        wintypes.HANDLE(parent),
        ctypes.pointer(unicode_name),
        _WIN_OBJ_CASE_INSENSITIVE,
        None,
        None,
    )
    status_block = _WinIoStatusBlock()
    result = wintypes.HANDLE()
    status = _NtCreateFile(
        ctypes.byref(result),
        desired_access,
        ctypes.byref(attributes),
        ctypes.byref(status_block),
        None,
        _WIN_FILE_ATTRIBUTE_NORMAL,
        _WIN_SHARE_ALL,
        create_disposition,
        create_options,
        None,
        0,
    )
    if status < 0:
        winerror = int(_RtlNtStatusToDosError(status))
        if winerror in {2, 3}:
            raise FileNotFoundError(winerror, os.strerror(winerror), name)
        raise OSError(winerror, str(ctypes.WinError(winerror)), name)
    return _handle_value(result)


def _win_open_parent(root: ScopedFilesystemRootV2, parts: tuple[str, ...]) -> int:
    current = root._duplicate_native()
    try:
        for part in parts:
            try:
                child = _win_open_relative(
                    current,
                    part,
                    desired_access=(
                        _WIN_FILE_LIST_DIRECTORY
                        | _WIN_FILE_TRAVERSE
                        | _WIN_FILE_READ_ATTRIBUTES
                        | _WIN_SYNCHRONIZE
                    ),
                    create_disposition=_WIN_FILE_OPEN,
                    create_options=(
                        _WIN_FILE_DIRECTORY_FILE
                        | _WIN_FILE_OPEN_REPARSE_POINT
                        | _WIN_FILE_OPEN_FOR_BACKUP_INTENT
                        | _WIN_FILE_SYNCHRONOUS_IO_NONALERT
                    ),
                )
            except OSError as error:
                _fail("TEVS_SCOPED_FS_PATH", f"scoped parent cannot be opened securely: {error}")
            try:
                _win_require_kind(_win_information(child), directory=True, path=part)
            except Exception:
                _win_close(child)
                raise
            _win_close(current)
            current = child
        return current
    except Exception:
        _win_close(current)
        raise


def _win_existing_bytes(parent: int, name: str, canonical: str, maximum: int) -> bytes | None:
    try:
        handle = _win_open_relative(
            parent,
            name,
            desired_access=_WIN_FILE_READ_DATA | _WIN_FILE_READ_ATTRIBUTES | _WIN_SYNCHRONIZE,
            create_disposition=_WIN_FILE_OPEN,
            create_options=(
                _WIN_FILE_NON_DIRECTORY_FILE
                | _WIN_FILE_OPEN_REPARSE_POINT
                | _WIN_FILE_SYNCHRONOUS_IO_NONALERT
            ),
        )
    except FileNotFoundError:
        return None
    except OSError as error:
        _fail("TEVS_SCOPED_FS_IO", f"existing scoped target {canonical!r} cannot be opened securely: {error}")
    try:
        _win_require_kind(_win_information(handle), directory=False, path=canonical)
        try:
            return _consume_bounded_v2(lambda count: _win_read(handle, count), maximum)
        except TevScriptError as error:
            if error.diagnostic.code == "TEVS_SCOPED_FS_BUDGET":
                return None
            raise
    finally:
        _win_close(handle)


def _win_replace(
    root: ScopedFilesystemRootV2,
    parts: tuple[str, ...],
    canonical: str,
    data: bytes,
) -> bool:
    parent = _win_open_parent(root, parts[:-1])
    temporary: int | None = None
    renamed = False
    try:
        if _win_existing_bytes(parent, parts[-1], canonical, len(data)) == data:
            return False
        for _attempt in range(128):
            temporary_name = f".{parts[-1]}.tev-v2-{secrets.token_hex(12)}.tmp"
            try:
                temporary = _win_open_relative(
                    parent,
                    temporary_name,
                    desired_access=(
                        _WIN_FILE_READ_DATA
                        | _WIN_FILE_WRITE_DATA
                        | _WIN_FILE_READ_ATTRIBUTES
                        | _WIN_DELETE
                        | _WIN_SYNCHRONIZE
                    ),
                    create_disposition=_WIN_FILE_CREATE,
                    create_options=(
                        _WIN_FILE_NON_DIRECTORY_FILE
                        | _WIN_FILE_OPEN_REPARSE_POINT
                        | _WIN_FILE_SYNCHRONOUS_IO_NONALERT
                    ),
                )
                break
            except FileExistsError:
                continue
            except OSError as error:
                if getattr(error, "winerror", None) == 80 or getattr(error, "errno", None) == 80:
                    continue
                _fail("TEVS_SCOPED_FS_IO", f"scoped temporary file cannot be created: {error}")
        if temporary is None:
            _fail("TEVS_SCOPED_FS_IO", "unable to reserve a unique scoped temporary file")
        _win_require_kind(_win_information(temporary), directory=False, path=canonical)
        _win_write_all(temporary, data)
        if not _FlushFileBuffers(wintypes.HANDLE(temporary)):
            _win_fail("TEVS_SCOPED_FS_IO", "scoped temporary flush failed")
        if not _SetFilePointerEx(wintypes.HANDLE(temporary), 0, None, _WIN_FILE_BEGIN):
            _win_fail("TEVS_SCOPED_FS_IO", "scoped temporary seek failed")
        verified = _consume_bounded_v2(lambda count: _win_read(temporary, count), len(data))
        if verified != data:
            _fail("TEVS_SCOPED_FS_VERIFY", "temporary file bytes do not match replacement data")
        _win_rename_relative(temporary, parent, parts[-1])
        renamed = True
        return True
    finally:
        if temporary is not None:
            if not renamed:
                _win_mark_delete(temporary)
            _win_close(temporary)
        _win_close(parent)


def _win_information(handle: int) -> _WinByHandleFileInformation:
    info = _WinByHandleFileInformation()
    if not _GetFileInformationByHandle(wintypes.HANDLE(handle), ctypes.byref(info)):
        _win_fail("TEVS_SCOPED_FS_IDENTITY", "cannot query filesystem object identity")
    return info


def _win_require_kind(info: _WinByHandleFileInformation, *, directory: bool, path: str) -> None:
    if info.dwFileAttributes & _WIN_FILE_ATTRIBUTE_REPARSE_POINT:
        _fail("TEVS_SCOPED_FS_ESCAPE", f"scoped filesystem object {path!r} is a reparse point")
    observed_directory = bool(info.dwFileAttributes & _WIN_FILE_ATTRIBUTE_DIRECTORY)
    if observed_directory != directory:
        expected = "directory" if directory else "regular file"
        _fail("TEVS_SCOPED_FS_KIND", f"scoped filesystem object {path!r} must be a {expected}")


def _win_final_path(handle: int) -> str:
    required = _GetFinalPathNameByHandleW(wintypes.HANDLE(handle), None, 0, 0)
    if required == 0:
        _win_fail("TEVS_SCOPED_FS_IDENTITY", "cannot size final filesystem path")
    buffer = ctypes.create_unicode_buffer(required + 1)
    written = _GetFinalPathNameByHandleW(wintypes.HANDLE(handle), buffer, len(buffer), 0)
    if written == 0 or written >= len(buffer):
        _win_fail("TEVS_SCOPED_FS_IDENTITY", "cannot query final filesystem path")
    return buffer.value


def _canonical_windows_final_path(path: str) -> str:
    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]
    return os.path.normcase(os.path.normpath(path)).replace("\\", "/")


def _win_read(handle: int, maximum: int) -> bytes:
    if maximum <= 0:
        return b""
    buffer = ctypes.create_string_buffer(maximum)
    observed = wintypes.DWORD()
    if not _ReadFile(
        wintypes.HANDLE(handle),
        buffer,
        maximum,
        ctypes.byref(observed),
        None,
    ):
        _win_fail("TEVS_SCOPED_FS_IO", "scoped file read failed")
    return buffer.raw[: observed.value]


def _win_write_all(handle: int, data: bytes) -> None:
    offset = 0
    while offset < len(data):
        chunk = data[offset : offset + _READ_CHUNK_BYTES]
        buffer = ctypes.create_string_buffer(chunk)
        written = wintypes.DWORD()
        if not _WriteFile(
            wintypes.HANDLE(handle),
            buffer,
            len(chunk),
            ctypes.byref(written),
            None,
        ):
            _win_fail("TEVS_SCOPED_FS_IO", "scoped temporary write failed")
        if written.value <= 0:
            _fail("TEVS_SCOPED_FS_IO", "scoped temporary write made no progress")
        offset += written.value


def _win_rename_relative(handle: int, parent: int, name: str) -> None:
    encoded = name.encode("utf-16-le")
    pointer_size = ctypes.sizeof(ctypes.c_void_p)
    root_offset = 8 if pointer_size == 8 else 4
    length_offset = root_offset + pointer_size
    name_offset = length_offset + 4
    structure_size = ((name_offset + 2 + pointer_size - 1) // pointer_size) * pointer_size
    raw = ctypes.create_string_buffer(structure_size + len(encoded))
    raw[0] = 1
    ctypes.c_void_p.from_buffer(raw, root_offset).value = parent
    wintypes.DWORD.from_buffer(raw, length_offset).value = len(encoded)
    ctypes.memmove(ctypes.addressof(raw) + name_offset, encoded, len(encoded))
    status_block = _WinIoStatusBlock()
    status = _NtSetInformationFile(
        wintypes.HANDLE(handle),
        ctypes.byref(status_block),
        raw,
        len(raw),
        _WIN_FILE_RENAME_INFORMATION,
    )
    if status < 0:
        winerror = int(_RtlNtStatusToDosError(status))
        _fail(
            "TEVS_SCOPED_FS_IO",
            f"scoped atomic replacement failed: {ctypes.WinError(winerror)}",
        )


def _win_mark_delete(handle: int) -> None:
    disposition = _WinFileDispositionInformation(True)
    _SetFileInformationByHandle(
        wintypes.HANDLE(handle),
        _WIN_FILE_DISPOSITION_INFO,
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
    )


def _win_close(handle: int) -> None:
    if handle:
        _CloseHandle(wintypes.HANDLE(handle))


def _handle_value(handle: object) -> int:
    value = ctypes.cast(handle, ctypes.c_void_p).value
    return 0 if value is None else int(value)


def _win_fail(code: str, message: str) -> None:
    error = ctypes.get_last_error()
    _fail(code, f"{message}: {ctypes.WinError(error)}")
