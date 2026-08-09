from __future__ import annotations

import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .diagnostics import TevScriptError
from .json_io import load_strict_json
from .types import Signature, SUPPORTED_TYPES

_SCHEMA = "TEV_SCRIPT_CAPABILITY_CATALOG_V1"
_STABLE_ID = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:/-]*$")
_KINDS = {"observation", "effect"}


def parse_capability_catalog(raw: Any) -> dict[str, tuple[Signature, ...]]:
    if not isinstance(raw, dict) or set(raw) != {"schema", "capabilities"}:
        raise TevScriptError(
            "TEVS_CAPABILITY_CATALOG_CONTRACT",
            "catalog must contain exactly schema and capabilities",
        )
    if raw["schema"] != _SCHEMA or not isinstance(raw["capabilities"], list):
        raise TevScriptError(
            "TEVS_CAPABILITY_CATALOG_CONTRACT",
            f"expected {_SCHEMA}",
        )
    result: dict[str, tuple[Signature, ...]] = {}
    for index, value in enumerate(raw["capabilities"]):
        path = f"capabilities[{index}]"
        if not isinstance(value, dict) or set(value) != {
            "capability_id",
            "parameters",
            "return_type",
            "kind",
        }:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_CONTRACT",
                f"{path} has an invalid field set",
            )
        capability_id = value["capability_id"]
        if not isinstance(capability_id, str) or _STABLE_ID.fullmatch(capability_id) is None:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_ID",
                f"{path}.capability_id is not a canonical stable id",
            )
        parameters = value["parameters"]
        if (
            not isinstance(parameters, list)
            or len(parameters) > 64
            or not all(isinstance(item, str) for item in parameters)
        ):
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                f"{path}.parameters must be a type-name array",
            )
        if any(item not in SUPPORTED_TYPES or item == "Unit" for item in parameters):
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                f"{path} has an unsupported parameter type",
            )
        return_type = value["return_type"]
        kind = value["kind"]
        if return_type not in SUPPORTED_TYPES or kind not in _KINDS:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                f"{path} has an unsupported return type or kind",
            )
        if capability_id in result:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_DUPLICATE",
                f"duplicate capability {capability_id}",
            )
        result[capability_id] = (
            Signature(tuple(parameters), str(return_type), str(kind)),
        )
    return result


def load_capability_catalog(path: str | Path) -> dict[str, tuple[Signature, ...]]:
    return parse_capability_catalog(load_strict_json(Path(path)))


def merge_capability_catalogs(
    base: Mapping[str, tuple[Signature, ...]],
    extra: Mapping[str, tuple[Signature, ...]] | None,
) -> dict[str, tuple[Signature, ...]]:
    result = dict(base)
    if extra is None:
        return result
    for capability_id, signatures in extra.items():
        if not isinstance(capability_id, str) or _STABLE_ID.fullmatch(capability_id) is None:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_ID",
                f"non-canonical capability id {capability_id!r}",
            )
        if not isinstance(signatures, tuple) or not signatures:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                f"capability {capability_id} requires at least one signature",
            )
        for signature in signatures:
            if not isinstance(signature, Signature):
                raise TevScriptError(
                    "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                    f"capability {capability_id} contains a non-Signature entry",
                )
            if (
                len(signature.parameters) > 64
                or any(item not in SUPPORTED_TYPES or item == "Unit" for item in signature.parameters)
                or signature.return_type not in SUPPORTED_TYPES
                or signature.kind not in _KINDS
            ):
                raise TevScriptError(
                    "TEVS_CAPABILITY_CATALOG_SIGNATURE",
                    f"capability {capability_id} contains an invalid signature",
                )
        existing = result.get(capability_id)
        if existing is not None and existing != signatures:
            raise TevScriptError(
                "TEVS_CAPABILITY_CATALOG_CONFLICT",
                f"capability {capability_id} conflicts with the portable catalog",
            )
        result[capability_id] = signatures
    return result
