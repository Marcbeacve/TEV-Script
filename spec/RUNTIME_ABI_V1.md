# TEV Script Runtime ABI V1

## Program loading

A runtime must:

1. decode valid UTF-8 and parse through the `TEV_CANONICAL_JSON_V1` strict
   input boundary;
2. validate `TEV_SCRIPT_PROGRAM_IR_V2` structure and exact opcode shapes;
3. verify `language_version=0.2.0`;
4. remove `semantic_hash`, `debug`, and `debug_hash`;
5. canonicalize the remaining object;
6. verify the SHA-256 semantic hash;
7. reject unknown opcodes, malformed values and duplicate identities.

## Capability binding

A capability is identified by a stable string and a signature embedded in the
program IR:

```text
capability_id
parameter types
return type
kind = observation | effect
```

Invocation is synchronous in ABI V1:

```text
invoke(arguments[]) → one typed value
```

`Unit` capabilities return the host's unit/null representation. A missing
capability is a terminal runtime error; no default physical effect is permitted.

## Events

`invoke(entity, event, arguments)` executes one bounded FIFO event chain.
Emitted events are recorded before a matching local handler is queued. Events
without a handler remain observable outputs.

## Determinism

The runtime must preserve:

- exact integer and rational arithmetic;
- source instruction order;
- FIFO emitted-event order;
- canonical entity/state ordering in receipts;
- fail-closed budget handling;
- no implicit capability calls.

Physical capability results can depend on the host. Conformance scenarios bind
controlled capabilities so runtimes can be compared byte-for-byte.
