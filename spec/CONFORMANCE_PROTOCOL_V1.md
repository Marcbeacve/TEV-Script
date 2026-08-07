# TEV Script Conformance Protocol V1

A conforming runtime consumes a validated program IR, controlled capability configuration and ordered event invocations, and emits `TEV_SCRIPT_CONFORMANCE_RECEIPT_V1` containing program hash, scenario id, final typed state, emitted events, capability trace and receipt hash. The receipt uses `TEV_CANONICAL_JSON_V1` followed by exactly one LF.

Input files pass the strict UTF-8/JSON boundary before execution. Duplicate members, floating-point structural numbers, negative zero, unsafe structural integers, malformed UTF-8 and malformed syntax are rejected.

## Positive authority

The authoritative positive campaign contains:

- `player.basic.v1`: lifecycle, state mutation, effects and emitted-event chaining;
- `matrix.full.v1`: all V0.2 binary/unary operators, pure functions, portable value kinds, typed event arguments, Unicode and controlled capability values;
- `player.idle.v1`: alternate Player control-flow branch;
- `event-chain.v1`: direct/local event chaining and typed emitted arguments.

Conforming implementations reproduce all four canonical receipt bytes exactly.

## Negative authority

`conformance/language-negative-v1.json` is normative. Its eight structurally admissible but operationally invalid handler mutations must be rejected before execution with `TEVS_IR_FLOW_INVALID`. The corpus covers stack underflow, definite local initialization, operator/type mismatch, CFG stack merge mismatch, capability argument type mismatch, conversion input mismatch, pure-call argument mismatch and reachable return-stack leak.

Runtime ABI must also reject non-canonical invocation ids and capability-binding ids rather than trimming or normalizing them. Strict JSON negatives and semantic/debug hash tampering remain mandatory.

A runtime is conformant only after canonical vectors, the four positive receipts, the shared eight-case IR-flow corpus, strict-input negatives and ABI fail-closed boundaries all pass.
