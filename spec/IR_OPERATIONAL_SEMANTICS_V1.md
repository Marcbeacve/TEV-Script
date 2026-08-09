# TEV Script IR Operational Semantics V1

This document is normative for `TEV_SCRIPT_PROGRAM_IR_V2` used by language version `0.2.0`.

## Abstract machine

Each handler executes with `(pc, stack, locals, parameters, entity-state, emitted-buffer)`. The operand stack is typed. Parameters and state exist before entry. Locals become readable only after a `STORE_LOCAL` on every control-flow path reaching the read.

Instructions execute in source/lowered order. All jumps are forward. A reachable handler path must terminate at `RETURN`; jumping to one-past-the-end is invalid IR. `RETURN` requires an empty operand stack.

## Instructions

- `CONST T V`: push decoded value `V:T`.
- `LOAD_STATE/LOCAL/PARAM name T`: push the named value with exact declared type. `LOAD_LOCAL` additionally requires definite initialization.
- `STORE_STATE/LOCAL name T`: pop exact `T`; store it. `STORE_LOCAL` marks that local initialized.
- `CONVERT_INT_TO_RAT`: pop Int and push its exact denominator-one Rat.
- `UNARY`: pop the operand required by the operator and push the declared result.
- `BINARY`: pop right then left, require the operator/type matrix from Static Semantics V1, push result.
- `CALL_PURE`: pop arguments in reverse stack order, invoke the normative pure function, push non-Unit result.
- `CALL_CAPABILITY`: pop arguments according to the entity capability declaration, invoke exactly that host binding, and push a successfully coerced non-Unit result.
- `EMIT_EVENT`: pop arguments according to the declared event signature and append the event to the handler emitted-buffer.
- `JUMP_IF_FALSE`: pop Bool and select fallthrough or target.
- `JUMP`: transfer to target.
- `RETURN`: terminate the handler; stack must be empty.

## Static flow verification

Before runtime construction, every handler is abstract-interpreted over its acyclic CFG. Every reachable instruction has a unique stack type vector. At a CFG merge, incoming stack vectors must be identical and definitely-initialized locals are intersected. Stack underflow, type mismatch, invalid operator signatures, local-before-store, merge mismatch, jump-to-exit and reachable stack leak are `TEVS_IR_FLOW_INVALID`.

This verification is normative, not an optimization. Python, JavaScript, C# and derived C# hosts must reject the same negative corpus before execution.

## Event machine

`invoke(entity,event,args)` validates canonical invocation identifiers and executes a bounded FIFO queue. A missing local handler is an observable emitted event. A handled emitted event is first recorded as emitted and then queued. The event-chain budget is checked before processing each queued event.

## Deterministic faults

Program/IR contract failures occur before execution. Runtime faults include missing capability, invalid invocation id, capability return coercion failure, instruction/event budget exhaustion and division by zero. Hosts must not repair malformed identifiers, substitute missing capabilities, or silently normalize inputs.
