from __future__ import annotations

LANGUAGE_VERSION = "0.2.0"
IR_SCHEMA = "TEV_SCRIPT_PROGRAM_IR_V2"

MAX_SOURCE_BYTES = 1_000_000
MAX_ENTITIES = 128
MAX_STATES_PER_ENTITY = 256
MAX_HANDLERS_PER_ENTITY = 256
MAX_LOCALS_PER_HANDLER = 256
MAX_ARGUMENTS = 64
MAX_INSTRUCTIONS_PER_HANDLER = 8192
MAX_EVENT_CHAIN = 128

TYPE_NAMES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3", "Unit"})
VALUE_TYPE_NAMES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3"})
CAPABILITY_KINDS = frozenset({"observation", "effect"})

BOUNDARY_FLAGS = (
    "dynamic_code",
    "reflection",
    "unbounded_loops",
    "implicit_physical_effects",
    "runtime_source_compilation",
    "automatic_authority_escalation",
)
