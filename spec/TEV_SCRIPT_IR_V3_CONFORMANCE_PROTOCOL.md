# TEV Script IR V3 cross-runtime conformance protocol

Status: **normative candidate V1**.

## Objective

Given one exact `TEV_SCRIPT_PROGRAM_IR_V3` artifact and one exact portable scenario, every conforming host must produce the same canonical receipt bytes. Parity is not defined as "similar final state"; it includes observable event order, capability-call order, canonical argument values, intermediate state hashes and final state.

## Scenario

Schema: `TEV_SCRIPT_IR_V3_SCENARIO_V1`.

A scenario binds:

- `scenario_id`;
- exact IR V3 `semantic_hash`;
- exact `source_semantic_hash`;
- a finite scripted capability transcript;
- a finite ordered list of external invocations.

Every scenario invocation argument is explicitly typed and canonically encoded. The runner must verify the type against the invoked handler signature or an explicitly declared emitted-event signature. No host-type inference is part of conformance.

## Scripted capabilities

Each capability id has a finite ordered list of expected calls. A call entry contains:

- exact typed canonical input arguments;
- for non-`Unit` return types, one exact typed canonical return value.

When the runtime invokes a scripted capability, the conformance host:

1. consumes the next expected call for that capability;
2. encodes actual runtime arguments using the program type table;
3. compares exact typed canonical arguments;
4. records the call in the receipt;
5. returns the scripted canonical value decoded through the same V3 value codec, or host `Unit` for a `Unit` capability.

Too many calls, too few calls, wrong order, wrong arguments, wrong return type, or undeclared capability access fail conformance.

## State witness

A state witness is sorted by entity id and state name. Each state entry contains explicit `type` and canonical V3 `value`.

`state_hash = SHA-256(canonical_json(state_witness))`.

The receipt includes the initial state hash, a state hash after every invocation step, and the complete final state witness plus its hash.

## Event witness

Every emitted event receipt contains:

- `entity_id`;
- `event_id`;
- ordered argument list;
- each argument's exact `type` and canonical V3 `value`.

Event order is semantic. Handled emitted events are recorded at emission time and may subsequently execute through the local FIFO event chain, matching the runtime event model.

## Receipt

Schema: `TEV_SCRIPT_IR_V3_CONFORMANCE_RECEIPT_V1`.

The receipt contains:

- scenario identity/hash;
- program/source semantic hashes;
- initial state hash;
- one ordered step receipt per invocation;
- ordered capability-call transcript;
- final state witness/hash;
- `receipt_hash` over the receipt body before adding `receipt_hash`.

Source paths, process ids, timestamps, locale, host version strings and wall-clock timing are excluded from canonical receipt semantics.

## Cross-host pass rule

For the same exact program bytes and scenario bytes:

```text
Python canonical receipt
== JavaScript canonical receipt
== C# canonical receipt
```

byte for byte.

A host that merely reaches the same final application state while differing in capability invocation count/order, emitted event order/types, intermediate state hash, canonical value representation or receipt hash is **not conformant**.

## Boundedness

- scenario invocation steps: maximum 1024;
- scripted calls per capability: maximum 4096;
- capability count: maximum 8192;
- invocation/capability arity: maximum 64;
- all nested values inherit target IR V3 `maximum_value_nesting`.

Budget excess is a conformance input error, never truncation.
