from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SourceUnit:
    path: str
    text: str

    @classmethod
    def from_bytes(cls, path: str, data: bytes) -> "SourceUnit":
        if b"\x00" in data:
            raise ValueError("source contains NUL bytes")
        return cls(path=path, text=data.decode("utf-8-sig"))
