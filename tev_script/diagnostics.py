from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class SourceSpan:
    path: str
    start_offset: int
    end_offset: int
    line: int
    column: int

    def to_dict(self) -> dict[str, int | str]:
        return {
            "path": self.path,
            "start_offset": self.start_offset,
            "end_offset": self.end_offset,
            "line": self.line,
            "column": self.column,
        }


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    message: str
    span: SourceSpan | None = None
    hint: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "span": None if self.span is None else self.span.to_dict(),
            "hint": self.hint,
        }


class TevScriptError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        span: SourceSpan | None = None,
        hint: str = "",
    ) -> None:
        self.diagnostic = Diagnostic(code, message, span, hint)
        location = ""
        if span is not None:
            location = f" at {span.path}:{span.line}:{span.column}"
        suffix = f" Hint: {hint}" if hint else ""
        super().__init__(f"{code}{location}: {message}.{suffix}")
