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

BACKEND_SCHEMA = "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V1"
WHEEL_TAG = "py3-none-any"
_MIN_ZIP_EPOCH = 315532800
_MAX_ZIP_EPOCH = 4354819198
_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _project_metadata(root: Path) -> dict[str, object]:
    document = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
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
        raise RuntimeError("SOURCE_DATE_EPOCH must be an integer") from exc
    if epoch < _MIN_ZIP_EPOCH or epoch > _MAX_ZIP_EPOCH:
        raise RuntimeError("SOURCE_DATE_EPOCH outside deterministic ZIP range")
    parts = time.gmtime(epoch)
    second = parts.tm_sec - (parts.tm_sec % 2)
    return (
        parts.tm_year,
        parts.tm_mon,
        parts.tm_mday,
        parts.tm_hour,
        parts.tm_min,
        second,
    )


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return "sha256=" + encoded


def _package_entries(root: Path) -> list[tuple[str, bytes]]:
    package_root = root / "tev_script"
    if not (package_root / "__init__.py").is_file():
        raise RuntimeError("tev_script package missing")
    entries: list[tuple[str, bytes]] = []
    unsupported: list[str] = []
    for path in sorted(package_root.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file():
            continue
        if path.is_symlink():
            raise RuntimeError("package symlinks are forbidden")
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


def _readme_metadata(
    project: dict[str, object],
    root: Path,
) -> tuple[str, str] | None:
    readme = project.get("readme")
    if readme is None:
        return None
    if not isinstance(readme, dict):
        raise RuntimeError("project.readme must be a table")
    if set(readme) != {"file", "content-type"}:
        raise RuntimeError("project.readme must contain file and content-type")
    file_name = _single_line(readme["file"], "project.readme.file")
    content_type = _single_line(
        readme["content-type"],
        "project.readme.content-type",
    )
    relative = Path(file_name)
    if relative.is_absolute() or ".." in relative.parts or "." in relative.parts:
        raise RuntimeError("unsafe project.readme.file")
    path = root / relative
    if not path.is_file() or path.is_symlink():
        raise RuntimeError("project.readme.file must be a regular file")
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        text += "\n"
    return content_type, text


def _metadata_bytes(project: dict[str, object], root: Path) -> bytes:
    name = _single_line(project["name"], "project.name")
    version = _version_component(_single_line(project["version"], "project.version"))
    lines = [
        "Metadata-Version: 2.1",
        "Name: " + name,
        "Version: " + version,
    ]
    description = project.get("description")
    if description is not None:
        lines.append("Summary: " + _single_line(description, "project.description"))
    requires_python = project.get("requires-python")
    if requires_python is not None:
        lines.append("Requires-Python: " + _single_line(requires_python, "project.requires-python"))
    dependencies = project.get("dependencies", [])
    if dependencies != []:
        raise RuntimeError("TEV Script reference wheel requires zero runtime dependencies")
    readme = _readme_metadata(project, root)
    if readme is None:
        return ("\n".join(lines) + "\n").encode("utf-8")
    content_type, body = readme
    lines.append("Description-Content-Type: " + content_type)
    return ("\n".join(lines) + "\n\n" + body).encode("utf-8")


def _wheel_bytes() -> bytes:
    return (
        "Wheel-Version: 1.0\n"
        "Generator: " + BACKEND_SCHEMA + "\n"
        "Root-Is-Purelib: true\n"
        "Tag: " + WHEEL_TAG + "\n"
    ).encode("utf-8")


def _entry_points_bytes(project: dict[str, object]) -> bytes | None:
    scripts = project.get("scripts", {})
    if not isinstance(scripts, dict):
        raise RuntimeError("project.scripts must be a table")
    if not scripts:
        return None
    lines = ["[console_scripts]"]
    for name in sorted(scripts):
        script_name = _single_line(name, "script name")
        target = _single_line(scripts[name], "script target")
        lines.append(f"{script_name} = {target}")
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


def build_wheel(
    wheel_directory: str,
    config_settings: object = None,
    metadata_directory: str | None = None,
) -> str:
    del config_settings, metadata_directory
    root = _project_root()
    project = _project_metadata(root)
    distribution = _distribution_component(_single_line(project["name"], "project.name"))
    version = _version_component(_single_line(project["version"], "project.version"))
    dist_info = f"{distribution}-{version}.dist-info"
    filename = f"{distribution}-{version}-{WHEEL_TAG}.whl"

    entries = _package_entries(root)
    entries.extend(
        (
            (f"{dist_info}/METADATA", _metadata_bytes(project, root)),
            (f"{dist_info}/WHEEL", _wheel_bytes()),
        )
    )
    entry_points = _entry_points_bytes(project)
    if entry_points is not None:
        entries.append((f"{dist_info}/entry_points.txt", entry_points))
    entries.sort(key=lambda item: item[0])

    record_path = f"{dist_info}/RECORD"
    record = _record_bytes(entries, record_path)
    entries.append((record_path, record))
    entries.sort(key=lambda item: item[0])

    destination = Path(wheel_directory)
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / filename
    if target.exists():
        raise RuntimeError("wheel destination already exists")

    timestamp = _zip_timestamp()
    with zipfile.ZipFile(target, mode="w", compression=zipfile.ZIP_STORED) as archive:
        for path, data in entries:
            archive.writestr(_zip_info(path, timestamp), data)

    return filename


def get_requires_for_build_wheel(config_settings: object = None) -> list[str]:
    del config_settings
    return []


__all__ = [
    "BACKEND_SCHEMA",
    "WHEEL_TAG",
    "build_wheel",
    "get_requires_for_build_wheel",
]
