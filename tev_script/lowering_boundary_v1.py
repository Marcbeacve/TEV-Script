from __future__ import annotations

from dataclasses import dataclass

from .ast_v1 import (
    AnimateStmt,
    AssignStmt,
    CallStmt,
    EmitStmt,
    Expr,
    ForStmt,
    IfStmt,
    LetStmt,
    LogStmt,
    MatchStmt,
    MoveStmt,
    ReturnStmt,
)
from .behavior_model_v1 import CompositeModelV1
from .static_semantics_v1 import StaticSemanticsV1

IR_V2_VALUE_TYPES = frozenset({"Bool", "Int", "Rat", "Text", "Vec2", "Vec3"})
IR_V2_SIGNATURE_TYPES = frozenset({*IR_V2_VALUE_TYPES, "Unit"})


@dataclass(frozen=True, slots=True)
class LoweringBlockerV1:
    code: str
    message: str
    component_id: str
    event_id: str | None = None

    def semantic_surface(self) -> dict[str, str | None]:
        return {
            "code": self.code,
            "message": self.message,
            "component_id": self.component_id,
            "event_id": self.event_id,
        }


@dataclass(frozen=True, slots=True)
class LoweringBoundaryV1:
    target_ir: str
    lowerable: bool
    blockers: tuple[LoweringBlockerV1, ...]

    def semantic_surface(self) -> dict[str, object]:
        return {
            "target_ir": self.target_ir,
            "lowerable": self.lowerable,
            "blockers": [item.semantic_surface() for item in self.blockers],
        }


def analyze_ir_v2_lowering_boundary(
    semantics: StaticSemanticsV1,
) -> LoweringBoundaryV1:
    blockers: list[LoweringBlockerV1] = []
    composite_summaries = {
        item.composite_id: item for item in semantics.composites
    }

    for model in semantics.behavior_model.composites:
        if model.kind != "entity":
            continue
        summary = composite_summaries[model.composite_id]

        for state_name, type_id in summary.states:
            if type_id not in IR_V2_VALUE_TYPES:
                blockers.append(
                    LoweringBlockerV1(
                        "TEVS_V1_LOWER_IR3_STATE_TYPE",
                        f"runtime state {state_name!r} uses {type_id}",
                        model.composite_id,
                    )
                )

        for handler in summary.handlers:
            for parameter_name, type_id in handler.parameters:
                if type_id not in IR_V2_VALUE_TYPES:
                    blockers.append(
                        LoweringBlockerV1(
                            "TEVS_V1_LOWER_IR3_EVENT_TYPE",
                            f"event parameter {parameter_name!r} uses {type_id}",
                            model.composite_id,
                            handler.event_id,
                        )
                    )
            for emitted_event, parameter_types in handler.emitted_events:
                for type_id in parameter_types:
                    if type_id not in IR_V2_VALUE_TYPES:
                        blockers.append(
                            LoweringBlockerV1(
                                "TEVS_V1_LOWER_IR3_EMITTED_TYPE",
                                f"emitted event {emitted_event!r} uses {type_id}",
                                model.composite_id,
                                handler.event_id,
                            )
                        )

            for capability_id in handler.capabilities:
                matching = [
                    item for item in semantics.types.capabilities
                    if item.callable_id == capability_id
                ]
                for signature in matching:
                    type_ids = [
                        *(item.type_id for item in signature.parameters),
                        signature.return_type.type_id,
                    ]
                    if any(type_id not in IR_V2_SIGNATURE_TYPES for type_id in type_ids):
                        blockers.append(
                            LoweringBlockerV1(
                                "TEVS_V1_LOWER_IR3_CAPABILITY_TYPE",
                                f"required capability {capability_id!r} uses a V1-only value type",
                                model.composite_id,
                                handler.event_id,
                            )
                        )

        _scan_entity_fragments(model, blockers)

    unique: dict[tuple[str, str, str, str | None], LoweringBlockerV1] = {}
    for item in blockers:
        key = (item.code, item.message, item.component_id, item.event_id)
        unique[key] = item
    ordered = tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                item.component_id,
                item.event_id or "",
                item.code,
                item.message,
            ),
        )
    )
    return LoweringBoundaryV1(
        "TEV_SCRIPT_PROGRAM_IR_V2",
        not ordered,
        ordered,
    )


def _scan_entity_fragments(
    model: CompositeModelV1,
    blockers: list[LoweringBlockerV1],
) -> None:
    for fragment in model.handler_fragments:
        event_id = fragment.declaration.event_id
        _scan_statements(
            fragment.declaration.body,
            model.composite_id,
            event_id,
            blockers,
        )


def _scan_statements(
    statements: tuple[object, ...],
    component_id: str,
    event_id: str,
    blockers: list[LoweringBlockerV1],
) -> None:
    for statement in statements:
        if isinstance(statement, LetStmt):
            _scan_expr(statement.expression, component_id, event_id, blockers)
        elif isinstance(statement, AssignStmt):
            _scan_expr(statement.expression, component_id, event_id, blockers)
        elif isinstance(statement, CallStmt):
            for argument in statement.arguments:
                _scan_expr(argument, component_id, event_id, blockers)
        elif isinstance(statement, EmitStmt):
            for argument in statement.arguments:
                _scan_expr(argument, component_id, event_id, blockers)
        elif isinstance(statement, (LogStmt, MoveStmt, AnimateStmt)):
            _scan_expr(statement.expression, component_id, event_id, blockers)
        elif isinstance(statement, IfStmt):
            _scan_expr(statement.condition, component_id, event_id, blockers)
            _scan_statements(statement.then_body, component_id, event_id, blockers)
            _scan_statements(statement.else_body, component_id, event_id, blockers)
        elif isinstance(statement, ForStmt):
            _scan_statements(statement.body, component_id, event_id, blockers)
        elif isinstance(statement, MatchStmt):
            blockers.append(
                LoweringBlockerV1(
                    "TEVS_V1_LOWER_IR3_MATCH",
                    "runtime match requires the IR V3 value/control profile",
                    component_id,
                    event_id,
                )
            )
            _scan_expr(statement.expression, component_id, event_id, blockers)
            for arm in statement.arms:
                _scan_statements(arm.body, component_id, event_id, blockers)
        elif isinstance(statement, ReturnStmt):
            continue
        else:
            raise TypeError(f"unsupported V1 statement {type(statement).__name__}")


def _scan_expr(
    root: Expr,
    component_id: str,
    event_id: str,
    blockers: list[LoweringBlockerV1],
) -> None:
    stack = [root]
    while stack:
        expression = stack.pop()
        if expression.kind in {"record", "enum", "some", "none", "ok", "err", "field"}:
            blockers.append(
                LoweringBlockerV1(
                    "TEVS_V1_LOWER_IR3_EXPRESSION",
                    f"runtime expression kind {expression.kind!r} requires IR V3 unless erased before handler lowering",
                    component_id,
                    event_id,
                )
            )
        if expression.kind == "record":
            _type_name, field_inits = expression.value
            stack.extend(field.expression for field in field_inits)
        stack.extend(expression.children)
