# TEV Script Program IR V4 Specification

## 1. Authority and purpose

Program IR V4 is the only V2 runtime input. It is a self-contained canonical JSON
artifact. A conforming runtime validates the complete artifact and all external pins
before executing any instruction, acquiring an observation, planning an effect, or
committing state.

The normative JSON structural envelope is
`schemas/tev-script-program-ir-v4.schema.json`. Schema validity is necessary but not
sufficient: the relational and hash rules in this document are mandatory.

## 2. Canonical profile

Canonical JSON uses UTF-8, sorted object keys, no insignificant whitespace, JSON
booleans/null, and ASCII escapes for non-ASCII code points. Duplicate object keys,
NaN, infinity, host integers outside the governed encoding, and trailing data are
invalid. A `program_ir_hash` is SHA-256 lowercase hexadecimal of the canonical object
with `program_ir_hash` omitted.

Every object has the exact field set for its schema. Unknown fields are invalid.
Arrays are ordered only as defined below; unordered semantic collections are sorted
before hashing.

## 3. Common envelope

Every profile contains:

```text
schema             versioned profile discriminator
source             source semantic identity
profile            execution profile
type_table         closed V4 type table
type_table_hash    hash of the governed table payload
program_ir_hash    hash of the complete body
```

`source.language_version` is exactly `2.0.0`. `source.semantic_hash` is an external
source-to-IR pin, not recomputed by the runtime. When an expected source or program
hash is supplied, comparison occurs before execution.

## 4. Type table and values

`type_table.boundary.maximum_value_nesting` is in `1..128`. `types` contains
`7..16384` descriptors sorted lexically by `type_id`. It contains exactly one
descriptor for each portable base type and all transitive dependencies.

Descriptor kinds and exact fields are:

```text
primitive: type_id, kind
unit:      type_id, kind
record:    type_id, kind, fields
enum:      type_id, kind, variants
option:    type_id, kind, argument
result:    type_id, kind, ok_type, err_type
list/set:  type_id, kind, element_type, capacity, order_policy
array:     type_id, kind, element_type, length, order_policy
map:       type_id, kind, key_type, value_type, capacity, order_policy
```

Record fields and enum variants are nonempty, unique, and lexically sorted. Option,
Result, List, Array, Set, and Map IDs must equal their normalized constructed spelling.
Capacities and lengths are in `1..4096`. Record/collection reference cycles are
invalid. `Unit` is not encodable.

Primitive values use the existing portable encodings: JSON booleans for `Bool`,
`{"$int":"…"}` for exact `Int`, normalized numerator/denominator encoding for `Rat`,
JSON strings for `Text`, and governed component objects for vectors. Algebraic and
collection values carry explicit discriminators and type identity. Decoding followed
by encoding must reproduce byte-identical canonical JSON.

## 5. Pure profile

```text
schema  = TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1
profile = pure
```

The source block additionally binds `entry_hash` and monomorphic `callable_id`.
`entry` contains name, typed parameters, return type, canonical body, body hash,
closed type roots/hash, static step upper bound, maximum steps, and typed encoded
arguments.

Validation recursively assigns one result type to every expression, verifies exact
operator signatures, collection capacity, field/method target, task DAG acyclicity,
and static step composition. The body result type equals `return_type`. Parameter and
argument name/type sequences are byte-identical. `maximum_steps` is not less than the
computed static bound. Evaluation counts each governed operation and fails before a
step beyond the maximum.

Pure evaluation cannot access a host capability or modify state.

## 6. Recursive profile

```text
schema  = TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1
profile = recursive
```

The common pure closure applies. `entry.recursion_contract` has exact fields:

```text
kind = decreases_int
measure_parameter
measure_parameter_index
measure_type = Int
max_depth
single_static_self_call = true
self_call_in_loops = false
self_call_in_conditions = false
local_static_step_upper_bound
recursive_static_step_upper_bound
maximum_steps
contract_hash
```

The measure index/name/type matches the parameter list. Each recursive edge decreases
the admitted measure. The body contains no indirect or mutual recursive edge. The
contract hash binds the canonical body and every bound. Runtime checks both call depth
and total steps before entry to the next recursive frame.

## 7. Effects profile

```text
schema  = TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1
profile = effects
```

The envelope additionally contains `state_schema`, `capabilities`, `action`,
`scenario`, and `execution`.

State slots are unique and sorted by name. `schema_hash` binds their name/type/initial
triples; `initial_state_hash` binds canonical initial values. `execution.current_state`
has exactly one correctly typed value for each slot.

Observation contracts are unique and sorted by capability ID. Each binds parameter
types, return type, kind `observation`, and `contract_hash`. `table_hash` binds the
canonical contract list. The scenario uses the exact same table hash and exactly one
lane per exercised capability. Calls are consumed in action order; each argument and
return value is decoded and re-encoded under the contract. Missing or extra calls are
invalid.

The action has a finite step list, typed parameters, static step upper bound,
observation-call upper bound, and action hash. Steps may compute pure values, consume
observations, or set state. State is committed only after all steps and transcript
checks succeed. The run receipt binds initial/final state, transcript, result bounds,
and all upstream hashes.

## 8. Effects R2 planning profile

```text
schema  = TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_R2_V1
profile = effects_r2_plan
```

R2 adds a closed `commands` table and `command_request_upper_bound`. Each command
contract binds ID, parameter types, kind `effect_command`, idempotency policy, and
contract hash. Action execution creates an ordered, content-addressed intent batch and
a proposed state transition. Planning is inert: it cannot call a provider, touch a
host object, or finalize state.

An authority grant is valid only when it binds the exact batch hash, provider
descriptor hash, authority scope hash, and complete allowed contract-hash set. A
provider observation is accepted only when every intent has a receipt bound to that
intent and the batch status is `PASS`. A failed or partial batch cannot finalize
state. Ledger replay returns an identical prior commit receipt and does not invoke the
provider twice.

## 9. Pure operation semantics

IR expressions use exact operation discriminators and exact field sets. Constants
are decoded through the declared type. Variables reference the closed lexical
environment. Arithmetic, comparison, conditionals, records, variants, fields,
collections, protocol specializations, task scopes, and bounded iteration follow
`TEV_SCRIPT_V2_LANGUAGE.md`.

Evaluation order is deterministic and left-to-right except task children, whose
physical order is nonsemantic. Task results are reassembled by canonical child index.
Priority selection orders by declared priority then lexical index. Losing speculative
branches expose no observation, state, intent, or receipt.

## 10. Hash closure

The validator recomputes and compares, where present:

- type-table hash and transitive type-closure hash;
- source semantic, entry, callable, expression, recursion-contract, state-schema,
  initial-state, capability-table, command-table, action, scenario, and program hashes;
- observation transcript and effect intent/batch/authority/provider receipt hashes;
- final run or transition receipt hash.

No supplied hash is trusted because its spelling is valid. Any mismatch fails before
the dependent object is used.

## 11. Budgets and failure

All arrays and recursive structures obey their schema bounds and the tighter static
bounds produced by validation. Runtime counters never wrap or saturate silently.
Malformed JSON, duplicate keys, unknown profiles or operations, unknown types,
noncanonical encodings, unsorted tables, type mismatch, cycle, exhausted budget,
missing capability, transcript drift, authority mismatch, partial commit, or hash
mismatch is a terminal failure with no finalized state.
