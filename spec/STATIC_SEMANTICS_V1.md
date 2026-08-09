# TEV Script Static Semantics V1

This document is normative for language version `0.2.0`.

## Compilation unit

V0.2 has one source file per program. Modules/imports are outside V0.2 rather than partially implemented.

## Names

Program, entity, state, handler, parameter and local names are canonical ASCII identifiers. Entity/state/handler names are unique in their declared scope. Parameters cannot shadow state. Locals cannot shadow state, parameters, or other locals. V0.2 locals are immutable and may be declared only in the handler top-level block.

## Types

Value types are `Bool`, `Int`, `Rat`, `Text`, `Vec2`, `Vec3`. `Unit` is a return-only type and cannot be state, parameter, local, or event argument storage. The only implicit widening is `Int -> Rat`.

## State

State initializers are compile-time literals: Bool, Int, Rat, Text, unary-minus numeric literal, `vec2` literal, or `vec3` literal. Runtime observation/effect calls are not state initializers.

## Operators

- `not Bool -> Bool`.
- unary `-` accepts `Int` or `Rat`.
- `and/or` accept `Bool,Bool -> Bool`.
- `==/!=` accept equal value types; numeric operands may first widen to Rat.
- `< <= > >=` accept numeric operands; mixed numeric operands widen to Rat.
- `+/-`: Int+Int -> Int, numeric -> Rat, equal Vec2/Vec3 -> same vector type.
- `*`: Int*Int -> Int, numeric -> Rat, vector*numeric or numeric*vector -> vector.
- `/`: numeric -> Rat, vector/numeric -> vector. Division by zero is a deterministic runtime fault.

Operands are evaluated left-to-right and eagerly. `and/or` are ordinary eager operators in V0.2, not short-circuit forms.

## Pure functions

`vec2(Rat,Rat)->Vec2`, `vec3(Rat,Rat,Rat)->Vec3`, `min(Int,Int)->Int`, `min(Rat,Rat)->Rat`, `max(Int,Int)->Int`, `max(Rat,Rat)->Rat`.

## Capabilities

The portable default catalog is `catalogs/portable_capabilities_v1.json`. A compiler may receive an additional `TEV_SCRIPT_CAPABILITY_CATALOG_V1`; additional entries may add stable ids or repeat an identical portable signature, but cannot redefine a portable id.

A capability signature is `(stable id, ordered parameter types, return type, kind)`, where kind is `observation|effect`. Every capability actually used by an entity is emitted into that entity's IR declaration. Unknown or signature-incompatible calls fail compilation.

The source grammar does not hard-code host namespaces. A source call such as `sensor.temperature()` is valid only when its signature is present in the compilation catalog.

## Events and control flow

Handlers are unique by event id. `start` and `update` have zero parameters. Emitted events have one consistent signature per entity and must agree with a same-named local handler. V0.2 emits only forward control-flow jumps; loops and recursion are outside the language boundary.

## Source-to-IR closure

A successful frontend compilation is not complete until the emitted `TEV_SCRIPT_PROGRAM_IR_V2` passes the same structural and flow verifier required of every runtime. A frontend must never return IR that a conforming runtime must reject.
