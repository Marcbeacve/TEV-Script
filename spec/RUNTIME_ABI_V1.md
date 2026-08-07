# TEV Script Runtime ABI V1

## Program loading

A runtime must:

1. decode valid UTF-8 and parse through the `TEV_CANONICAL_JSON_V1` strict input boundary;
2. validate `TEV_SCRIPT_PROGRAM_IR_V2` structure and exact opcode shapes;
3. run the normative typed CFG/stack verifier from `IR_OPERATIONAL_SEMANTICS_V1`;
4. verify `language_version=0.2.0`;
5. remove `semantic_hash`, `debug`, and `debug_hash`;
6. canonicalize the remaining object;
7. verify the SHA-256 semantic hash;
8. reject unknown opcodes, malformed values and duplicate identities.

No program reaches runtime construction after a structural or flow-verification failure.

## Canonical identifiers

Runtime invocation entity/event ids use `[A-Za-z_][A-Za-z0-9_]*`. Capability binding ids use `^[A-Za-z_][A-Za-z0-9_.:/-]*$`. Hosts reject non-canonical ids; trimming, case folding, Unicode normalization and other silent repair are forbidden.

## Capability binding

A capability is identified by a stable string and a signature embedded in program IR: ordered parameter types, return type and `kind = observation | effect`. Invocation is synchronous: `invoke(arguments[]) -> one typed value`. Unit capabilities return the host unit/null representation. Missing bindings fail closed; non-Unit results must coerce to the declared TEV type or fail. No default physical effect is permitted.

## Events

`invoke(entity,event,arguments)` executes one bounded FIFO event chain. Emitted events are recorded before a matching local handler is queued. Events without a handler remain observable outputs.

## Determinism

The runtime preserves exact integer/rational arithmetic, instruction order, eager expression semantics, FIFO emitted-event order, canonical entity/state ordering in receipts, fail-closed budgets, and no implicit capability calls. Physical capability results may depend on the host; conformance binds controlled capabilities when byte equality is required.

## ABI V1 boundaries

ABI V1 is synchronous and bounded. Async tasks/promises, runtime source compilation, reflection, backward jumps, recursion and automatic authority escalation are outside ABI V1 and cannot be introduced by host convention.
