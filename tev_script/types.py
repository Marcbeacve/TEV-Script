from __future__ import annotations

from dataclasses import dataclass


SUPPORTED_TYPES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"})


@dataclass(frozen=True, slots=True)
class Signature:
    parameters: tuple[str, ...]
    return_type: str
    kind: str


CAPABILITIES: dict[str, tuple[Signature, ...]] = {
    "debug.log": (Signature(("Text",), "Unit", "effect"),),
    "input.move2d": (Signature((), "Vec2", "observation"),),
    "time.delta": (Signature((), "Rat", "observation"),),
    "motion.move2d": (
        Signature(("Vec2",), "Unit", "effect"),
    ),
    "animation.play": (
        Signature(("Text",), "Unit", "effect"),
    ),
}

PURE_FUNCTIONS: dict[str, tuple[Signature, ...]] = {
    "vec2": (Signature(("Rat", "Rat"), "Vec2", "pure"),),
    "vec3": (Signature(("Rat", "Rat", "Rat"), "Vec3", "pure"),),
    "max": (
        Signature(("Int", "Int"), "Int", "pure"),
        Signature(("Rat", "Rat"), "Rat", "pure"),
    ),
    "min": (
        Signature(("Int", "Int"), "Int", "pure"),
        Signature(("Rat", "Rat"), "Rat", "pure"),
    ),
}


def is_numeric(type_name: str) -> bool:
    return type_name in {"Int", "Rat"}


def can_widen(actual: str, expected: str) -> bool:
    return actual == expected or (actual == "Int" and expected == "Rat")


def select_signature(
    signatures: tuple[Signature, ...],
    actual: tuple[str, ...],
) -> Signature | None:
    exact = [item for item in signatures if item.parameters == actual]
    if exact:
        return exact[0]
    widened = [
        item
        for item in signatures
        if len(item.parameters) == len(actual)
        and all(can_widen(a, e) for a, e in zip(actual, item.parameters, strict=True))
    ]
    return widened[0] if len(widened) == 1 else None
