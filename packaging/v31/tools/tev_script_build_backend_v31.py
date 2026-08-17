from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


BACKEND_SCHEMA = "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V31"
WHEEL_TAG = "py3-none-any"


def _packaging_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _load_stable_backend() -> ModuleType:
    repo_root = Path(__file__).resolve().parents[3]
    path = repo_root / "packaging/v3/tools/tev_script_build_backend_v3.py"
    if not path.is_file():
        raise RuntimeError("stable V3 deterministic wheel backend missing")
    spec = importlib.util.spec_from_file_location(
        "tev_script_build_backend_v3_for_v31",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load stable V3 deterministic wheel backend")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if getattr(module, "BACKEND_SCHEMA", None) != "TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V3":
        raise RuntimeError("stable V3 wheel backend identity mismatch")
    if getattr(module, "WHEEL_TAG", None) != WHEEL_TAG:
        raise RuntimeError("stable V3 wheel tag mismatch")
    module.BACKEND_SCHEMA = BACKEND_SCHEMA
    module._packaging_root = _packaging_root
    return module


def build_wheel(
    wheel_directory: str,
    config_settings: object = None,
    metadata_directory: str | None = None,
) -> str:
    backend = _load_stable_backend()
    return backend.build_wheel(
        wheel_directory,
        config_settings=config_settings,
        metadata_directory=metadata_directory,
    )


def get_requires_for_build_wheel(config_settings: object = None) -> list[str]:
    del config_settings
    return []


__all__ = [
    "BACKEND_SCHEMA",
    "WHEEL_TAG",
    "build_wheel",
    "get_requires_for_build_wheel",
]
