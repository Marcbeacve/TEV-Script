from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical import MAX_STRUCTURAL_INTEGER
from .diagnostics import TevScriptError


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise TevScriptError(
                "TEVS_JSON_DUPLICATE_KEY",
                f"duplicate JSON object member {key!r}",
            )
        result[key] = value
    return result


def _parse_structural_integer(text: str) -> int:
    if text == "-0":
        raise TevScriptError(
            "TEVS_JSON_NEGATIVE_ZERO",
            "negative zero is not a canonical structural integer",
        )
    value = int(text, 10)
    if not -MAX_STRUCTURAL_INTEGER <= value <= MAX_STRUCTURAL_INTEGER:
        raise TevScriptError(
            "TEVS_JSON_NUMBER_RANGE",
            "JSON structural integer exceeds the portable safe range",
        )
    return value


def _reject_float(text: str) -> Any:
    raise TevScriptError(
        "TEVS_JSON_FLOAT_FORBIDDEN",
        f"floating-point JSON number {text!r} is forbidden",
    )


def parse_strict_json(text: str) -> Any:
    """Parse the TEV JSON input domain without lossy host-language coercions."""
    try:
        return json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_int=_parse_structural_integer,
            parse_float=_reject_float,
            parse_constant=lambda token: (_raise_constant(token)),
        )
    except TevScriptError:
        raise
    except json.JSONDecodeError as error:
        raise TevScriptError(
            "TEVS_JSON_SYNTAX",
            f"invalid JSON at line {error.lineno}, column {error.colno}: {error.msg}",
        ) from error


def _raise_constant(token: str) -> Any:
    raise TevScriptError(
        "TEVS_JSON_CONSTANT_FORBIDDEN",
        f"non-standard JSON constant {token!r} is forbidden",
    )


def load_strict_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as error:
        raise TevScriptError(
            "TEVS_JSON_UTF8",
            "JSON input must be valid UTF-8",
        ) from error
    return parse_strict_json(text)
