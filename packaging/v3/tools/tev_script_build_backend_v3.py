from __future__ import annotations

import base64
import csv
import hashlib
import io
import os
from pathlib import Path
import re
import time
import tomllib
import zipfile

BACKEND_SCHEMA = "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V3"
WHEEL_TAG = "py3-none-any"
_MIN_ZIP_EPOCH = 315532800
_MAX_ZIP_EPOCH = 4354819198
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")


def _packaging_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _project_metadata() -> dict[str, object]:
    document = tomllib.loads((_packaging_root() / "pyproject.toml").read_text(encoding="utf-8"))
    project = document.get("project")
    if not isinstance(project, dict):
        raise RuntimeError("pyproject project table missing")
    return project


def _single_line(value: object, name: str) -> str:
    text = str(value)
    if not text or "\r" in text or "\n" in text:
        raise RuntimeError(f"invalid {name}")
    return text


def _distribution_component(value: str) -> str:
    normalized = re.sub(r"[-_.]+", "_", value).strip("_")
    if not normalized:
        raise RuntimeError("empty distribution component")
    return normalized


def _version_component(value: str) -> str:
    if _VERSION.fullmatch(value) is None:
        raise RuntimeError("unsupported TEV Script package version")
    return value


def _zip_timestamp() -> tuple[int, int, int, int, int, int]:
    raw = os.environ.get("SOURCE_DATE_EPOCH")
    if raw is None:
        raise RuntimeError("SOURCE_DATE_EPOCH required")
    try:
        epoch = int(raw)
    except ValueError as exc:
        raise RuntimeError("SOURCE_DATE_EPOCH must be integer") from exc
    if not _MIN_ZIP_EPOCH <= epoch <= _MAX_ZIP_EPOCH:
        raise RuntimeError("SOURCE_DATE_EPOCH outside deterministic ZIP range")
    parts = time.gmtime(epoch)
    return (parts.tm_year, parts.tm_mon, parts.tm_mday, parts.tm_hour, parts.tm_min, parts.tm_sec - parts.tm_sec % 2)


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _package_entries() -> list[tuple[str, bytes]]:
    root = _repo_root()
    package_root = root / "tev_script"
    if not (package_root / "__init__.py").is_file():
        raise RuntimeError("tev_script package missing")
    entries: list[tuple[str, bytes]] = []
    unsupported: list[str] = []
    for path in sorted(package_root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise RuntimeError("package symlinks forbidden")
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        relative = path.relative_to(root).as_posix()
        if path.suffix != ".py":
            unsupported.append(relative)
            continue
        entries.append((relative, path.read_bytes()))
    if unsupported:
        raise RuntimeError("unsupported package resources: " + ",".join(unsupported))
    return entries


def _metadata_bytes(project: dict[str, object]) -> bytes:
    name = _single_line(project["name"], "project.name")
    version = _version_component(_single_line(project["version"], "project.version"))
    lines = ["Metadata-Version: 2.1", "Name: " + name, "Version: " + version]
    if project.get("description") is not None:
        lines.append("Summary: " + _single_line(project["description"], "project.description"))
    if project.get("requires-python") is not None:
        lines.append("Requires-Python: " + _single_line(project["requires-python"], "project.requires-python"))
    if project.get("dependencies", []) != []:
        raise RuntimeError("V3 wheel requires zero runtime dependencies")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _wheel_bytes() -> bytes:
    return ("Wheel-Version: 1.0\nGenerator: " + BACKEND_SCHEMA + "\nRoot-Is-Purelib: true\nTag: " + WHEEL_TAG + "\n").encode("utf-8")


def _entry_points_bytes(project: dict[str, object]) -> bytes | None:
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict):
        raise RuntimeError("project.scripts must be table")
    if not scripts:
        return None
    lines = ["[console_scripts]"]
    for name in sorted(scripts):
        lines.append(f"{_single_line(name, 'script name')} = {_single_line(scripts[name], 'script target')}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def _record_bytes(entries: list[tuple[str, bytes]], record_path: str) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    for path, data in entries:
        writer.writerow((path, _record_hash(data), str(len(data))))
    writer.writerow((record_path, "", ""))
    return buffer.getvalue().encode("utf-8")


def _zip_info(path: str, timestamp: tuple[int, int, int, int, int, int]) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(path, date_time=timestamp)
    info.create_system = 3
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = (0o100644 & 0xFFFF) << 16
    return info


def build_wheel(wheel_directory: str, config_settings: object = None, metadata_directory: str | None = None) -> str:
    del config_settings, metadata_directory
    project = _project_metadata()
    distribution = _distribution_component(_single_line(project["name"], "project.name"))
    version = _version_component(_single_line(project["version"], "project.version"))
    dist_info = f"{distribution}-{version}.dist-info"
    filename = f"{distribution}-{version}-{WHEEL_TAG}.whl"
    entries = _package_entries()
    entries.extend(((f"{dist_info}/METADATA", _metadata_bytes(project)), (f"{dist_info}/WHEEL", _wheel_bytes())))
    entry_points = _entry_points_bytes(project)
    if entry_points is not None:
        entries.append((f"{dist_info}/entry_points.txt", entry_points))
    entries.sort(key=lambda item: item[0])
    record_path = f"{dist_info}/RECORD"
    entries.append((record_path, _record_bytes(entries, record_path)))
    entries.sort(key=lambda item: item[0])
    destination = Path(wheel_directory)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    if target.exists():
        raise RuntimeError("wheel destination already exists")
    timestamp = _zip_timestamp()
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for path, data in entries:
            archive.writestr(_zip_info(path, timestamp), data)
    return filename


def get_requires_for_build_wheel(config_settings: object = None) -> list[str]:
    del config_settings
    return []


__all__ = ["BACKEND_SCHEMA", "WHEEL_TAG", "build_wheel", "get_requires_for_build_wheel"]
