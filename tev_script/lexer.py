from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from .diagnostics import SourceSpan, TevScriptError
from .source import SourceUnit

KEYWORDS = {
    "script": "SCRIPT",
    "version": "VERSION",
    "entity": "ENTITY",
    "state": "STATE",
    "on": "ON",
    "let": "LET",
    "if": "IF",
    "else": "ELSE",
    "call": "CALL",
    "emit": "EMIT",
    "return": "RETURN",
    "true": "TRUE",
    "false": "FALSE",
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "log": "LOG",
    "move": "MOVE",
    "animate": "ANIMATE",
}

TWO_CHAR = {
    "==": "EQEQ",
    "!=": "NE",
    "<=": "LE",
    ">=": "GE",
}

ONE_CHAR = {
    "{": "LBRACE",
    "}": "RBRACE",
    "(": "LPAREN",
    ")": "RPAREN",
    ":": "COLON",
    ";": "SEMI",
    ",": "COMMA",
    ".": "DOT",
    "=": "EQUAL",
    "+": "PLUS",
    "-": "MINUS",
    "*": "STAR",
    "/": "SLASH",
    "<": "LT",
    ">": "GT",
}


@dataclass(frozen=True, slots=True)
class Token:
    kind: str
    text: str
    span: SourceSpan


class Lexer:
    def __init__(self, source: SourceUnit) -> None:
        self.source = source
        self.text = source.text
        self.index = 0
        self.line = 1
        self.column = 1

    def tokenize(self) -> tuple[Token, ...]:
        tokens: list[Token] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            if char in " \t\r\n":
                self._advance(char)
                continue
            if char == "#":
                self._skip_comment()
                continue
            start = self._mark()
            pair = self.text[self.index : self.index + 2]
            if pair in TWO_CHAR:
                self._advance(pair[0])
                self._advance(pair[1])
                tokens.append(self._token(TWO_CHAR[pair], pair, start))
                continue
            if char in ONE_CHAR:
                self._advance(char)
                tokens.append(self._token(ONE_CHAR[char], char, start))
                continue
            if char == '"':
                tokens.append(self._string(start))
                continue
            if _is_ascii_digit(char):
                tokens.append(self._number(start))
                continue
            if _is_ascii_identifier_start(char):
                tokens.append(self._identifier(start))
                continue
            if char.isalpha() or char.isdigit():
                raise TevScriptError(
                    "TEVS_LEX_IDENTIFIER_NON_ASCII",
                    f"identifier characters must be ASCII, got {char!r}",
                    self._span(start),
                )
            raise TevScriptError(
                "TEVS_LEX_UNKNOWN_CHARACTER",
                f"unexpected character {char!r}",
                self._span(start),
            )
        eof = self._mark()
        tokens.append(self._token("EOF", "", eof))
        return tuple(tokens)

    def _mark(self) -> tuple[int, int, int]:
        return self.index, self.line, self.column

    def _span(self, start: tuple[int, int, int]) -> SourceSpan:
        return SourceSpan(
            path=self.source.path,
            start_offset=start[0],
            end_offset=self.index,
            line=start[1],
            column=start[2],
        )

    def _token(
        self,
        kind: str,
        text: str,
        start: tuple[int, int, int],
    ) -> Token:
        return Token(kind, text, self._span(start))

    def _advance(self, char: str) -> None:
        self.index += 1
        if char == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1

    def _skip_comment(self) -> None:
        while self.index < len(self.text) and self.text[self.index] != "\n":
            self._advance(self.text[self.index])

    def _identifier(self, start: tuple[int, int, int]) -> Token:
        while self.index < len(self.text):
            char = self.text[self.index]
            if not _is_ascii_identifier_continue(char):
                break
            self._advance(char)
        value = self.text[start[0] : self.index]
        return self._token(KEYWORDS.get(value, "IDENT"), value, start)

    def _number(self, start: tuple[int, int, int]) -> Token:
        while self.index < len(self.text) and _is_ascii_digit(self.text[self.index]):
            self._advance(self.text[self.index])
        kind = "INT"
        if (
            self.index < len(self.text)
            and self.text[self.index] == "."
            and self.index + 1 < len(self.text)
            and _is_ascii_digit(self.text[self.index + 1])
        ):
            kind = "DECIMAL"
            self._advance(".")
            while self.index < len(self.text) and _is_ascii_digit(self.text[self.index]):
                self._advance(self.text[self.index])
        return self._token(kind, self.text[start[0] : self.index], start)

    def _string(self, start: tuple[int, int, int]) -> Token:
        self._advance('"')
        result: list[str] = []
        while self.index < len(self.text):
            char = self.text[self.index]
            if char == '"':
                self._advance(char)
                return self._token("STRING", "".join(result), start)
            if char == "\n":
                raise TevScriptError(
                    "TEVS_LEX_STRING_NEWLINE",
                    "string literal cannot cross a line",
                    self._span(start),
                )
            if char == "\\":
                self._advance(char)
                if self.index >= len(self.text):
                    break
                escaped = self.text[self.index]
                replacements = {
                    "n": "\n",
                    "r": "\r",
                    "t": "\t",
                    '"': '"',
                    "\\": "\\",
                }
                if escaped not in replacements:
                    raise TevScriptError(
                        "TEVS_LEX_STRING_ESCAPE",
                        f"unsupported string escape \\{escaped}",
                        self._span(start),
                    )
                result.append(replacements[escaped])
                self._advance(escaped)
                continue
            result.append(char)
            self._advance(char)
        raise TevScriptError(
            "TEVS_LEX_STRING_UNTERMINATED",
            "unterminated string literal",
            self._span(start),
        )


def _is_ascii_digit(char: str) -> bool:
    return "0" <= char <= "9"


def _is_ascii_identifier_start(char: str) -> bool:
    return ("A" <= char <= "Z") or ("a" <= char <= "z") or char == "_"


def _is_ascii_identifier_continue(char: str) -> bool:
    return _is_ascii_identifier_start(char) or _is_ascii_digit(char)


def decimal_fraction(text: str) -> Fraction:
    whole, fractional = text.split(".", 1)
    denominator = 10 ** len(fractional)
    return Fraction(int(whole) * denominator + int(fractional), denominator)
