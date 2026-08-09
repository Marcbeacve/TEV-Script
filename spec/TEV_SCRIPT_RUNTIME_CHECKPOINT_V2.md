# TEV Script Runtime Checkpoint V2

Status: **normative V1 / IR V3 candidate**.

`TEV_SCRIPT_RUNTIME_CHECKPOINT_V2` extends the exact-restore principle of the certified V0.2 checkpoint without modifying `TEV_SCRIPT_RUNTIME_CHECKPOINT_V1`.

## Purpose

Checkpoint V2 serializes only deterministic language state required to continue one exact validated IR V3 program. It is not a heap dump, host-object serializer, migration format, hot-update format, or authority token.

## Canonical object

```json
{
  "schema": "TEV_SCRIPT_RUNTIME_CHECKPOINT_V2",
  "program_id": "Root",
  "ir_schema": "TEV_SCRIPT_PROGRAM_IR_V3",
  "semantic_hash": "<IR V3 semantic SHA-256>",
  "source_schema": "TEV_SCRIPT_LINKED_PROGRAM_V1",
  "source_semantic_hash": "<source semantic SHA-256>",
  "entities": [
    {
      "entity_id": "Player",
      "state": {
        "mode": {
          "type": "game.Mode",
          "value": {"$enum":{"type":"game.Mode","variant":"Run"}}
        }
      }
    }
  ]
}
```

The byte representation is the repository canonical JSON profile. Parsing a semantically equivalent but non-canonical JSON byte sequence fails closed.

## Identity binding

Restore requires exact equality of:

1. `program_id`;
2. IR schema (`TEV_SCRIPT_PROGRAM_IR_V3`);
3. IR V3 `semantic_hash`;
4. source semantic schema;
5. source semantic hash;
6. entity id set;
7. state-name set for every entity;
8. declared state type for every state.

A checkpoint therefore cannot be restored into a program merely because its visible states happen to look compatible. Program migration is a different protocol.

## State values

Every state value uses the exact IR V3 canonical value codec and the exact declared `type_id`.

Consequences:

- primitives remain compatible with V0.2 primitive encoding;
- records preserve nominal encoded type and canonical field order;
- enum/Option/Result preserve their nominal/constructed type and variant;
- `Unit` can never occur as checkpoint state;
- host-native object references are impossible;
- malformed nested values fail before runtime state mutation.

## Ordering and budgets

- entities are strictly sorted by `entity_id`;
- state is encoded as a canonical JSON object, therefore state keys are canonical lexical object keys;
- entity count is bounded by the runtime entity budget (128);
- state count per entity is bounded by 256;
- nested value depth is bounded by the target IR V3 `maximum_value_nesting`.

## Checkpoint hash

`checkpoint_hash = SHA-256(canonical_checkpoint_json_bytes)`.

The hash is a witness over the complete checkpoint object. It is not stored inside the checkpoint because doing so would create recursive self-hashing.

## Restore transaction

Restore is fail-before-mutation:

1. validate the target IR V3 and source binding;
2. verify all checkpoint identity fields;
3. verify exact entity/state/type sets;
4. decode every state value into temporary state using the target type table;
5. construct a fresh runtime;
6. install the fully decoded state only after every prior check passes.

No partial state restore is conformant.

## Explicit non-goals

Checkpoint V2 does not define:

- migration between semantic hashes;
- rollback-resistant storage;
- distributed checkpoint consensus;
- encryption/signing at rest;
- capability-provider state;
- external world state;
- in-flight host calls;
- threads/tasks/coroutines.

Those require separate protocols and must not be inferred from checkpoint success.
