from __future__ import annotations

import re
from pathlib import Path

from .ast_v1 import ModuleUnit, ScriptUnit, SourceFile
from .contracts_v1 import MAX_SOURCE_BYTES, V0_2_LANGUAGE_VERSION, V1_LANGUAGE_VERSION
from .diagnostics import TevScriptError
from .lexer_v1 import LexerV1, Token
from .parser_v1 import ParserV1
from .source import SourceUnit
from .syntax_validation_v1 import validate_v1_syntax_budgets

_ASCII_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def parse_v1_bytes(path: str, data: bytes) -> SourceFile:
    """Parse one exact V1 source unit; no linking or static semantics are performed."""
    if len(data) > MAX_SOURCE_BYTES:
        raise TevScriptError(
            "TEVS_V1_SOURCE_BUDGET",
            f"source exceeds {MAX_SOURCE_BYTES} bytes",
        )
    source = _decode_source(path, data)
    tokens = LexerV1(source).tokenize()
    declaration = ParserV1(tokens).parse_source_file()
    if declaration.language_version != V1_LANGUAGE_VERSION:
        raise TevScriptError(
            "TEVS_V1_VERSION_UNSUPPORTED",
            f"V1 source requires version {V1_LANGUAGE_VERSION}, got {declaration.language_version}",
            declaration.span,
        )
    validate_v1_syntax_budgets(declaration)
    return declaration


def parse_v1_path(path: str | Path) -> SourceFile:
    selected = Path(path)
    return parse_v1_bytes(selected.as_posix(), selected.read_bytes())


def parse_versioned_bytes(path: str, data: bytes) -> object:
    """Dispatch V0.2 scripts unchanged and V1 script/module units to the V1 parser.

    This function is intentionally parser-only. It does not alter the certified V0.2
    compiler entry points, and V1 compilation/linking remains a separate phase.
    """
    if len(data) > MAX_SOURCE_BYTES:
        raise TevScriptError(
            "TEVS_SOURCE_BUDGET",
            f"source exceeds {MAX_SOURCE_BYTES} bytes",
        )
    source = _decode_source(path, data)
    tokens = LexerV1(source).tokenize()
    kind, version = _source_header(tokens)
    if kind == "script" and version == V0_2_LANGUAGE_VERSION:
        # Lazy imports preserve the exact certified V0.2 parser path and avoid
        # V1 keyword classification affecting V0.2 identifiers.
        from .lexer import Lexer
        from .parser import Parser

        return Parser(Lexer(source).tokenize()).parse_script()
    if version != V1_LANGUAGE_VERSION:
        raise TevScriptError(
            "TEVS_SOURCE_VERSION_UNSUPPORTED",
            f"unsupported TEV Script source version {version}",
            tokens[0].span,
        )
    declaration = ParserV1(tokens).parse_source_file()
    if kind == "module" and not isinstance(declaration, ModuleUnit):
        raise AssertionError("source header/parser kind disagreement")
    if kind == "script" and not isinstance(declaration, ScriptUnit):
        raise AssertionError("source header/parser kind disagreement")
    validate_v1_syntax_budgets(declaration)
    return declaration


def parse_versioned_path(path: str | Path) -> object:
    selected = Path(path)
    return parse_versioned_bytes(selected.as_posix(), selected.read_bytes())


def _decode_source(path: str, data: bytes) -> SourceUnit:
    try:
        return SourceUnit.from_bytes(path, data)
    except UnicodeDecodeError as exc:
        raise TevScriptError(
            "TEVS_SOURCE_UTF8",
            "source must be valid UTF-8 (optional BOM allowed)",
        ) from exc
    except ValueError as exc:
        raise TevScriptError("TEVS_SOURCE_NUL", str(exc)) from exc


def _source_header(tokens: tuple[Token, ...]) -> tuple[str, str]:
    if not tokens:
        raise TevScriptError("TEVS_SOURCE_HEADER", "empty token stream")
    first = tokens[0]
    if first.text == "script":
        if (
            len(tokens) < 5
            or not _ASCII_IDENT.fullmatch(tokens[1].text)
            or tokens[2].text != "version"
            or tokens[3].kind != "STRING"
            or tokens[4].kind != "SEMI"
        ):
            raise TevScriptError(
                "TEVS_SOURCE_HEADER",
                "expected script IDENT version STRING ;",
                first.span,
            )
        return "script", tokens[3].text
    if first.text == "module":
        index = 1
        if index >= len(tokens) or not _ASCII_IDENT.fullmatch(tokens[index].text):
            raise TevScriptError(
                "TEVS_SOURCE_HEADER",
                "module requires a qualified module id",
                first.span,
            )
        index += 1
        while index + 1 < len(tokens) and tokens[index].kind == "DOT":
            if not _ASCII_IDENT.fullmatch(tokens[index + 1].text):
                break
            index += 2
        if (
            index + 2 >= len(tokens)
            or tokens[index].text != "version"
            or tokens[index + 1].kind != "STRING"
            or tokens[index + 2].kind != "SEMI"
        ):
            raise TevScriptError(
                "TEVS_SOURCE_HEADER",
                "expected module qualified.name version STRING ;",
                first.span,
            )
        return "module", tokens[index + 1].text
    raise TevScriptError(
        "TEVS_SOURCE_HEADER",
        "source must begin with script or module",
        first.span,
    )
