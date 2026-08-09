from __future__ import annotations

import re
from fractions import Fraction
from typing import Any

from .diagnostics import TevScriptError

_CANONICAL_INTEGER = re.compile(r"^-?(0|[1-9][0-9]*)$")


def _canonical_integer_text(value: Any, *, code: str) -> str:
    if not isinstance(value, str) or _CANONICAL_INTEGER.fullmatch(value) is None or value == "-0":
        raise TevScriptError(code, "integer text is not canonical")
    return value


def _runtime_integer(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError("bool is not Int")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(_canonical_integer_text(value, code="TEVS_RUNTIME_INT"), 10)
    raise TypeError("expected Int")


def _runtime_rational(value: Any) -> Fraction:
    if isinstance(value, Fraction):
        return value
    if isinstance(value, bool):
        raise TypeError("bool is not Rat")
    if isinstance(value, int):
        return Fraction(value, 1)
    if isinstance(value, str):
        return Fraction(int(_canonical_integer_text(value, code="TEVS_RUNTIME_RAT"), 10), 1)
    raise TypeError("expected Rat")


def encode_typed_value(type_name: str, value: Any) -> Any:
    if type_name == "Int":
        integer = _runtime_integer(value)
        return {"$int": str(integer)}
    if type_name == "Rat":
        rational = _runtime_rational(value)
        return {"$rat": [str(rational.numerator), str(rational.denominator)]}
    if type_name in {"Vec2", "Vec3"}:
        expected = 2 if type_name == "Vec2" else 3
        if not isinstance(value, (tuple, list)) or len(value) != expected:
            raise TypeError(f"expected {type_name}")
        return [encode_typed_value("Rat", item) for item in value]
    if type_name == "Bool":
        if not isinstance(value, bool):
            raise TypeError("expected Bool")
        return value
    if type_name == "Text":
        if not isinstance(value, str):
            raise TypeError("expected Text")
        return value
    if type_name == "Unit":
        if value is not None:
            raise TypeError("expected Unit")
        return None
    raise TevScriptError("TEVS_VALUE_TYPE", f"unknown type {type_name}")


def decode_typed_value(type_name: str, raw: Any) -> Any:
    if type_name == "Int":
        if not isinstance(raw, dict) or set(raw) != {"$int"}:
            raise TevScriptError("TEVS_RUNTIME_INT", "invalid integer value")
        text = _canonical_integer_text(raw["$int"], code="TEVS_RUNTIME_INT")
        return int(text, 10)
    if type_name == "Rat":
        if not isinstance(raw, dict) or set(raw) != {"$rat"}:
            raise TevScriptError("TEVS_RUNTIME_RAT", "invalid rational value")
        pair = raw["$rat"]
        if not isinstance(pair, list) or len(pair) != 2:
            raise TevScriptError("TEVS_RUNTIME_RAT", "invalid rational pair")
        numerator_text = _canonical_integer_text(pair[0], code="TEVS_RUNTIME_RAT")
        denominator_text = _canonical_integer_text(pair[1], code="TEVS_RUNTIME_RAT")
        try:
            result = Fraction(int(numerator_text, 10), int(denominator_text, 10))
        except ZeroDivisionError as error:
            raise TevScriptError("TEVS_RUNTIME_RAT", "invalid rational pair") from error
        if str(result.numerator) != numerator_text or str(result.denominator) != denominator_text:
            raise TevScriptError("TEVS_RUNTIME_RAT", "rational must be normalized")
        return result
    if type_name in {"Vec2", "Vec3"}:
        expected = 2 if type_name == "Vec2" else 3
        if not isinstance(raw, list) or len(raw) != expected:
            raise TevScriptError("TEVS_RUNTIME_VECTOR", f"invalid {type_name} value")
        return tuple(decode_typed_value("Rat", item) for item in raw)
    if type_name == "Bool":
        if not isinstance(raw, bool):
            raise TevScriptError("TEVS_RUNTIME_BOOL", "invalid boolean value")
        return raw
    if type_name == "Text":
        if not isinstance(raw, str):
            raise TevScriptError("TEVS_RUNTIME_TEXT", "invalid text value")
        return raw
    if type_name == "Unit":
        if raw is not None:
            raise TevScriptError("TEVS_RUNTIME_UNIT", "invalid unit value")
        return None
    raise TevScriptError("TEVS_RUNTIME_TYPE", f"unknown type {type_name}")
