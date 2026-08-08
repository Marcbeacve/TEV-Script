from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Mapping

from .canonical import canonical_hash, canonical_json
from .diagnostics import TevScriptError
from .ir_v3_validation import validate_program_ir_v3
from .ir_v3_values import decode_v3_value, encode_v3_value
from .json_io import parse_strict_json
from .runtime_v3 import CapabilityV3, ScriptRuntimeV3

_SCHEMA = "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2"
_HASH = re.compile(r"^[0-9a-f]{64}$")
_LOCAL = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_ROOT_KEYS = {
    "schema", "program_id", "ir_schema", "semantic_hash",
    "source_schema", "source_semantic_hash", "entities",
}


@dataclass(frozen=True, slots=True)
class RuntimeCheckpointV2:
    program_id: str
    ir_schema: str
    semantic_hash: str
    source_schema: str
    source_semantic_hash: str
    entities: tuple[tuple[str, tuple[tuple[str, str, Any], ...]], ...]

    @classmethod
    def capture(cls, runtime: ScriptRuntimeV3) -> "RuntimeCheckpointV2":
        entities: list[tuple[str, tuple[tuple[str, str, Any], ...]]] = []
        for entity_id in sorted(runtime.entities):
            entity = runtime.entities[entity_id]
            state: list[tuple[str, str, Any]] = []
            for state_name in sorted(entity.state):
                type_id = entity.state_types[state_name]
                state.append(
                    (
                        state_name,
                        type_id,
                        encode_v3_value(
                            type_id,
                            entity.state[state_name],
                            runtime.type_table,
                            context=f"checkpoint {entity_id}.{state_name}",
                        ),
                    )
                )
            entities.append((entity_id, tuple(state)))
        return cls(
            str(runtime.ir["program_id"]),
            str(runtime.ir["schema"]),
            str(runtime.ir["semantic_hash"]),
            str(runtime.ir["source_schema"]),
            str(runtime.ir["source_semantic_hash"]),
            tuple(entities),
        )

    @classmethod
    def parse(cls, text: str) -> "RuntimeCheckpointV2":
        parsed = parse_strict_json(text)
        canonical = canonical_json(parsed)
        if canonical != text:
            raise TevScriptError(
                "TEVS_CHECKPOINT_V2_CANONICAL",
                "runtime checkpoint must use exact canonical JSON bytes",
            )
        root = _object(parsed, "$")
        _exact_keys(root, "$", _ROOT_KEYS)
        if root["schema"] != _SCHEMA:
            _fail("TEVS_CHECKPOINT_V2_SCHEMA", "$.schema", f"expected {_SCHEMA}")
        program_id = _local(root["program_id"], "$.program_id")
        ir_schema = _string(root["ir_schema"], "$.ir_schema")
        if ir_schema != "TEV_SCRIPT_PROGRAM_IR_V3":
            _fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "expected TEV_SCRIPT_PROGRAM_IR_V3")
        semantic_hash = _sha(root["semantic_hash"], "$.semantic_hash")
        source_schema = _string(root["source_schema"], "$.source_schema")
        if source_schema not in {"TEV_SCRIPT_LINKED_PROGRAM_V1", "TEV_SCRIPT_PROGRAM_IR_V2"}:
            _fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", f"unsupported source schema {source_schema!r}")
        source_hash = _sha(root["source_semantic_hash"], "$.source_semantic_hash")

        raw_entities = _array(root["entities"], "$.entities")
        entities: list[tuple[str, tuple[tuple[str, str, Any], ...]]] = []
        previous_entity: str | None = None
        entity_ids: set[str] = set()
        for index, raw_entity in enumerate(raw_entities):
            path = f"$.entities[{index}]"
            entity = _object(raw_entity, path)
            _exact_keys(entity, path, {"entity_id", "state"})
            entity_id = _local(entity["entity_id"], path + ".entity_id")
            if entity_id in entity_ids or (previous_entity is not None and entity_id <= previous_entity):
                _fail("TEVS_CHECKPOINT_V2_ENTITY_ORDER", path + ".entity_id", "entities must be unique and strictly sorted")
            entity_ids.add(entity_id)
            previous_entity = entity_id
            raw_state = _object(entity["state"], path + ".state")
            state: list[tuple[str, str, Any]] = []
            for state_name in sorted(raw_state):
                _local(state_name, path + ".state key")
                typed = _object(raw_state[state_name], path + f".state.{state_name}")
                _exact_keys(typed, path + f".state.{state_name}", {"type", "value"})
                state.append((state_name, _string(typed["type"], path + f".state.{state_name}.type"), typed["value"]))
            entities.append((entity_id, tuple(state)))
        return cls(program_id, ir_schema, semantic_hash, source_schema, source_hash, tuple(entities))

    def to_object(self) -> dict[str, object]:
        return {
            "schema": _SCHEMA,
            "program_id": self.program_id,
            "ir_schema": self.ir_schema,
            "semantic_hash": self.semantic_hash,
            "source_schema": self.source_schema,
            "source_semantic_hash": self.source_semantic_hash,
            "entities": [
                {
                    "entity_id": entity_id,
                    "state": {
                        state_name: {"type": type_id, "value": value}
                        for state_name, type_id, value in state
                    },
                }
                for entity_id, state in self.entities
            ],
        }

    def to_canonical_json(self) -> str:
        return canonical_json(self.to_object())

    @property
    def checkpoint_hash(self) -> str:
        return canonical_hash(self.to_object())

    def restore_exact(
        self,
        ir: Mapping[str, Any],
        capabilities: Mapping[str, CapabilityV3] | None = None,
    ) -> ScriptRuntimeV3:
        target = dict(ir)
        table = validate_program_ir_v3(
            target,
            expected_source_semantic_hash=self.source_semantic_hash,
        )
        if str(target["program_id"]) != self.program_id:
            _fail("TEVS_CHECKPOINT_V2_PROGRAM_ID", "$.program_id", "checkpoint program id does not match target")
        if str(target["schema"]) != self.ir_schema:
            _fail("TEVS_CHECKPOINT_V2_IR_SCHEMA", "$.ir_schema", "checkpoint IR schema does not match target")
        if str(target["semantic_hash"]) != self.semantic_hash:
            _fail("TEVS_CHECKPOINT_V2_SEMANTIC_HASH", "$.semantic_hash", "checkpoint semantic hash does not match target")
        if str(target["source_schema"]) != self.source_schema:
            _fail("TEVS_CHECKPOINT_V2_SOURCE_SCHEMA", "$.source_schema", "checkpoint source schema does not match target")
        if str(target["source_semantic_hash"]) != self.source_semantic_hash:
            _fail("TEVS_CHECKPOINT_V2_SOURCE_HASH", "$.source_semantic_hash", "checkpoint source hash does not match target")

        expected_entities = {str(entity["entity_id"]): entity for entity in target["entities"]}
        checkpoint_entities = {entity_id: state for entity_id, state in self.entities}
        if set(expected_entities) != set(checkpoint_entities):
            _fail("TEVS_CHECKPOINT_V2_ENTITY_SET", "$.entities", "checkpoint entity set does not exactly match target")

        decoded_state: dict[str, dict[str, Any]] = {}
        for entity_id in sorted(expected_entities):
            definition = expected_entities[entity_id]
            expected_states = {str(state["name"]): str(state["type"]) for state in definition["states"]}
            checkpoint_state = {name: (type_id, value) for name, type_id, value in checkpoint_entities[entity_id]}
            if set(expected_states) != set(checkpoint_state):
                _fail("TEVS_CHECKPOINT_V2_STATE_SET", f"entity {entity_id}", "checkpoint state set does not exactly match target")
            decoded_state[entity_id] = {}
            for state_name in sorted(expected_states):
                expected_type = expected_states[state_name]
                observed_type, raw_value = checkpoint_state[state_name]
                if observed_type != expected_type:
                    _fail(
                        "TEVS_CHECKPOINT_V2_STATE_TYPE",
                        f"{entity_id}.{state_name}",
                        f"expected {expected_type}, got {observed_type}",
                    )
                decoded_state[entity_id][state_name] = decode_v3_value(
                    expected_type,
                    raw_value,
                    table,
                    context=f"checkpoint {entity_id}.{state_name}",
                )

        runtime = ScriptRuntimeV3(
            target,
            capabilities,
            expected_source_semantic_hash=self.source_semantic_hash,
        )
        for entity_id, values in decoded_state.items():
            runtime.entities[entity_id].state.clear()
            runtime.entities[entity_id].state.update(values)
        return runtime


def _fail(code: str, path: str, message: str) -> None:
    raise TevScriptError(code, f"{path}: {message}")


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict) or not all(isinstance(key, str) for key in value):
        _fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected object")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected array")
    return value


def _exact_keys(value: Mapping[str, Any], path: str, expected: set[str]) -> None:
    observed = set(value)
    if observed != expected:
        _fail("TEVS_CHECKPOINT_V2_SHAPE", path, f"field set mismatch; missing={sorted(expected-observed)}, extra={sorted(observed-expected)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        _fail("TEVS_CHECKPOINT_V2_SHAPE", path, "expected string")
    return value


def _local(value: Any, path: str) -> str:
    result = _string(value, path)
    if _LOCAL.fullmatch(result) is None:
        _fail("TEVS_CHECKPOINT_V2_IDENTIFIER", path, f"expected identifier, got {result!r}")
    return result


def _sha(value: Any, path: str) -> str:
    result = _string(value, path)
    if _HASH.fullmatch(result) is None:
        _fail("TEVS_CHECKPOINT_V2_SHA256", path, "expected lowercase SHA-256")
    return result
