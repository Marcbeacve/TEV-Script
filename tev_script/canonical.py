from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from typing import Any

MAX_STRUCTURAL_INTEGER = 2**53 - 1


def to_json_value(value: Any) -> Any:
    if isinstance(value, Fraction):
        return {"$rat": [str(value.numerator), str(value.denominator)]}
    if isinstance(value, tuple):
        return [to_json_value(item) for item in value]
    if isinstance(value, list):
        return [to_json_value(item) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("canonical object keys must be strings")
            result[key] = to_json_value(item)
        return result
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        if not -MAX_STRUCTURAL_INTEGER <= value <= MAX_STRUCTURAL_INTEGER:
            raise ValueError("structural integer exceeds the portable safe range")
        return value
    raise TypeError(f"unsupported canonical value {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        to_json_value(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()
