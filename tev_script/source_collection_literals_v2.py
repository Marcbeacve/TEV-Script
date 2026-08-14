from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .diagnostics import TevScriptError
from .ir_v4_values import (
    ArrayValueV4,
    ListValueV4,
    MapValueV4,
    RecordValueV4,
    SetValueV4,
    TypeTableV4,
    VariantValueV4,
    encode_v4_value,
)

_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


@dataclass(frozen=True, slots=True)
class ContextualLiteralV2:
    type_id: str
    value: Any
    encoded: Any
    semantic_hash: str


@dataclass(frozen=True, slots=True)
class _Token:
    kind: str
    text: str
    value: Any
    offset: int


def parse_contextual_literal_v2(
    text: str,
    expected_type: str,
    table: TypeTableV4,
    *,
    constructor_names: Mapping[str, Sequence[str]] | None = None,
) -> ContextualLiteralV2:
    """Parse one V2 literal under an exact expected V4 type.

    Collection capacity/length and ordering are never inferred from surface syntax.
    The expected type is authority for List/Array/Set/Map identity.
    """

    if not isinstance(text, str) or not text.strip():
        _fail("TEVS_V2_LITERAL_SYNTAX", "literal text must be non-empty")
    if not isinstance(expected_type, str) or not expected_type:
        _fail("TEVS_V2_LITERAL_EXPECTED_TYPE", "an exact expected type is required")
    table.require(expected_type, context="V2 contextual literal")
    parser = _LiteralParser(_tokenize(text), table, constructor_names or {})
    value = parser.parse(expected_type)
    encoded = encode_v4_value(expected_type, value, table, context="V2 contextual literal")
    canonical = json.dumps(
        {"type": expected_type, "value": encoded},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return ContextualLiteralV2(
        expected_type,
        value,
        encoded,
        hashlib.sha256(canonical).hexdigest(),
    )


class _LiteralParser:
    def __init__(
        self,
        tokens: tuple[_Token, ...],
        table: TypeTableV4,
        constructor_names: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self.tokens = tokens
        self.table = table
        self.constructor_names = {key: tuple(value) for key, value in (constructor_names or {}).items()}
        self.index = 0

    def parse(self, expected_type: str) -> Any:
        value = self._value(expected_type, 1)
        self._expect("EOF")
        return value

    def _value(self, type_id: str, depth: int) -> Any:
        if depth > self.table.maximum_value_nesting:
            _fail("TEVS_V2_LITERAL_NESTING", f"literal nesting exceeds {self.table.maximum_value_nesting}")
        descriptor = self.table.require(type_id, context="V2 literal")
        kind = descriptor.kind
        if kind == "primitive":
            return self._primitive(type_id, depth)
        if kind == "unit":
            _fail("TEVS_V2_LITERAL_UNIT", "Unit is not a literal value")
        if kind == "record":
            self._expect_type_name(type_id)
            self._expect("LPAREN")
            fields: dict[str, Any] = {}
            field_types = dict(descriptor.fields)
            if not self._at("RPAREN"):
                while True:
                    field = self._expect("IDENT").text
                    if "." in field:
                        _fail("TEVS_V2_LITERAL_RECORD_FIELD", "record field name must be local")
                    if field not in field_types:
                        _fail("TEVS_V2_LITERAL_RECORD_FIELD", f"unknown record field {field!r}")
                    if field in fields:
                        _fail("TEVS_V2_LITERAL_RECORD_FIELD", f"duplicate record field {field!r}")
                    self._expect("EQUAL")
                    fields[field] = self._value(field_types[field], depth + 1)
                    if not self._match("COMMA"):
                        break
                    if self._at("RPAREN"):
                        break
            self._expect("RPAREN")
            required = {name for name, _ in descriptor.fields}
            if set(fields) != required:
                missing = sorted(required - set(fields))
                _fail("TEVS_V2_LITERAL_RECORD_FIELD", f"missing record fields {missing}")
            return RecordValueV4(type_id, tuple((name, fields[name]) for name, _ in descriptor.fields))
        if kind == "enum":
            self._expect_type_name(type_id)
            self._expect("DCOLON")
            variant = self._expect("IDENT").text
            if "." in variant or variant not in descriptor.variants:
                _fail("TEVS_V2_LITERAL_ENUM_VARIANT", f"unknown enum variant {variant!r}")
            return VariantValueV4(type_id, variant)
        if kind == "option":
            assert descriptor.argument is not None
            if self._match_ident("None"):
                return VariantValueV4(type_id, "None")
            self._expect_ident("Some")
            self._expect("LPAREN")
            payload = self._value(descriptor.argument, depth + 1)
            self._expect("RPAREN")
            return VariantValueV4(type_id, "Some", payload)
        if kind == "result":
            assert descriptor.ok_type is not None and descriptor.err_type is not None
            token = self._expect("IDENT")
            if token.text == "Ok":
                payload_type = descriptor.ok_type
            elif token.text == "Err":
                payload_type = descriptor.err_type
            else:
                _fail("TEVS_V2_LITERAL_RESULT_VARIANT", "Result literal requires Ok(...) or Err(...)")
            self._expect("LPAREN")
            payload = self._value(payload_type, depth + 1)
            self._expect("RPAREN")
            return VariantValueV4(type_id, token.text, payload)
        if kind == "list":
            assert descriptor.element_type is not None
            items = self._sequence("LBRACKET", "RBRACKET", descriptor.element_type, depth)
            return ListValueV4(type_id, items)
        if kind == "array":
            assert descriptor.element_type is not None and descriptor.length is not None
            items = self._sequence("LBRACKET", "RBRACKET", descriptor.element_type, depth)
            if len(items) != descriptor.length:
                _fail("TEVS_V2_LITERAL_ARRAY_LENGTH", f"{type_id} requires exactly {descriptor.length} items, got {len(items)}")
            return ArrayValueV4(type_id, items)
        if kind == "set":
            assert descriptor.element_type is not None
            self._expect_ident("set")
            items = self._sequence("LBRACE", "RBRACE", descriptor.element_type, depth)
            return SetValueV4(type_id, items)
        if kind == "map":
            assert descriptor.key_type is not None and descriptor.value_type is not None
            self._expect_ident("map")
            self._expect("LBRACE")
            entries: list[tuple[Any, Any]] = []
            if not self._at("RBRACE"):
                while True:
                    key = self._value(descriptor.key_type, depth + 1)
                    self._expect("COLON")
                    value = self._value(descriptor.value_type, depth + 1)
                    entries.append((key, value))
                    if not self._match("COMMA"):
                        break
                    if self._at("RBRACE"):
                        break
            self._expect("RBRACE")
            return MapValueV4(type_id, tuple(entries))
        raise AssertionError(kind)

    def _primitive(self, type_id: str, depth: int) -> Any:
        if type_id == "Int":
            token = self._expect("NUMBER")
            if "." in token.text:
                _fail("TEVS_V2_LITERAL_TYPE", "Int literal cannot contain a decimal point")
            return int(token.text, 10)
        if type_id == "Rat":
            return Fraction(self._expect("NUMBER").text)
        if type_id == "Text":
            return self._expect("STRING").value
        if type_id == "Bool":
            token = self._expect("IDENT")
            if token.text == "true":
                return True
            if token.text == "false":
                return False
            _fail("TEVS_V2_LITERAL_TYPE", "Bool literal requires true or false")
        if type_id in {"Vec2", "Vec3"}:
            arity = 2 if type_id == "Vec2" else 3
            self._expect_ident(type_id.lower())
            self._expect("LPAREN")
            values: list[Any] = []
            for index in range(arity):
                if index:
                    self._expect("COMMA")
                values.append(self._value("Rat", depth + 1))
            self._expect("RPAREN")
            return tuple(values)
        _fail("TEVS_V2_LITERAL_TYPE", f"unsupported primitive literal type {type_id!r}")

    def _sequence(self, open_kind: str, close_kind: str, element_type: str, depth: int) -> tuple[Any, ...]:
        self._expect(open_kind)
        items: list[Any] = []
        if not self._at(close_kind):
            while True:
                items.append(self._value(element_type, depth + 1))
                if not self._match("COMMA"):
                    break
                if self._at(close_kind):
                    break
        self._expect(close_kind)
        return tuple(items)

    def _expect_type_name(self, type_id: str) -> None:
        token = self._expect("IDENT")
        aliases = self.constructor_names.get(type_id)
        if aliases is None:
            local = type_id.rsplit(".", 1)[-1]
            allowed = (type_id, local)
        else:
            allowed = tuple(dict.fromkeys((type_id, *aliases)))
        if token.text not in allowed:
            _fail(
                "TEVS_V2_LITERAL_NOMINAL_TYPE",
                f"expected constructor for {type_id!r} from {allowed}, got {token.text!r}",
            )

    def _expect_ident(self, text: str) -> None:
        token = self._expect("IDENT")
        if token.text != text:
            _fail("TEVS_V2_LITERAL_SYNTAX", f"expected {text!r}, got {token.text!r}")

    def _match_ident(self, text: str) -> bool:
        if self._at("IDENT") and self._current().text == text:
            self.index += 1
            return True
        return False

    def _current(self) -> _Token:
        return self.tokens[self.index]

    def _at(self, kind: str) -> bool:
        return self._current().kind == kind

    def _match(self, kind: str) -> bool:
        if self._at(kind):
            self.index += 1
            return True
        return False

    def _expect(self, kind: str) -> _Token:
        token = self._current()
        if token.kind != kind:
            _fail("TEVS_V2_LITERAL_SYNTAX", f"expected {kind}, got {token.kind} at offset {token.offset}")
        self.index += 1
        return token


def _tokenize(text: str) -> tuple[_Token, ...]:
    tokens: list[_Token] = []
    i = 0
    punctuation = {
        "[": "LBRACKET", "]": "RBRACKET", "{": "LBRACE", "}": "RBRACE",
        "(": "LPAREN", ")": "RPAREN", ",": "COMMA", ":": "COLON", "=": "EQUAL",
    }
    decoder = json.JSONDecoder()
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        if text.startswith("::", i):
            tokens.append(_Token("DCOLON", "::", None, i)); i += 2; continue
        if text[i] == '"':
            try:
                value, consumed = decoder.raw_decode(text[i:])
            except json.JSONDecodeError as exc:
                _fail("TEVS_V2_LITERAL_STRING", f"invalid string literal at offset {i}: {exc.msg}")
            if not isinstance(value, str):
                _fail("TEVS_V2_LITERAL_STRING", "literal must be a string")
            raw = text[i:i+consumed]
            tokens.append(_Token("STRING", raw, value, i)); i += consumed; continue
        match = _NUMBER.match(text, i)
        if match is not None:
            raw = match.group(0)
            tokens.append(_Token("NUMBER", raw, raw, i)); i = match.end(); continue
        match = _IDENT.match(text, i)
        if match is not None:
            raw = match.group(0)
            tokens.append(_Token("IDENT", raw, raw, i)); i = match.end(); continue
        kind = punctuation.get(text[i])
        if kind is not None:
            tokens.append(_Token(kind, text[i], None, i)); i += 1; continue
        _fail("TEVS_V2_LITERAL_SYNTAX", f"invalid literal token at offset {i}")
    tokens.append(_Token("EOF", "", None, len(text)))
    return tuple(tokens)


def _fail(code: str, message: str) -> None:
    raise TevScriptError(code, message)
