# TEVScript MAX 3.0.0 — Program IR V5 Semantic Process Profile

Status: normative implementation candidate for the MAX branch. It grants no stable or publication authority.

## 1. Purpose

IR V5 is additive over V2 Program IR V4. The first V5 profile closes semantic Field/Transformation execution and open-ended bounded processes. V2 pure computation remains an independently validated computational substrate until later V5 Total-Core profiles are admitted.

The profile discriminator is:

```text
schema  = TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1
profile = semantic_process
source.language_version = 3.0.0
```

A runtime validates the complete artifact before executing an instruction.

## 2. Program

A semantic-process program binds:

```text
program_id
source_semantic_hash
initial_field
transformations[]
instructions[]
entry_pc
quantum_step_limit
authority_hash
program_hash
```

`initial_field` is `SemanticFieldV1`. `transformations` is a closed unique table of `FieldTransformationV1` values addressed by `transformation_hash`.

The first profile admits only transformations whose `proof_requirement_hashes` are empty. A proof-open transformation is valid semantic data but is not executable in this profile until a later proof-admission layer resolves it.

`quantum_step_limit` is in `1..1_000_000`.

## 3. Instructions

The closed V1 instruction set is:

```text
apply
    transformation_hash
    next_pc

branch_fact
    fact_hash
    present_pc
    absent_pc

jump
    target_pc

halt
```

All targets are valid instruction indices. `apply` executes the exact closed Field delta. `branch_fact` checks fact-hash membership only. `jump` may form cycles. `halt` terminates the process.

There is no unbounded instruction execution inside an epoch.

## 4. Process checkpoint

A checkpoint binds:

```text
program_hash
field
pc
next_epoch_index
previous_continuation | null
checkpoint_hash
```

Process state identity is:

```text
Hash(program_hash, field_hash, pc)
```

For epoch zero, `previous_continuation` is null and `next_epoch_index=0`.

For every later checkpoint:

```text
previous_continuation.epoch_index == next_epoch_index - 1
previous_continuation.state_hash == current process-state identity
```

A checkpoint cannot be resumed under a different program hash.

## 5. Quantum execution

`run_semantic_quantum(program, checkpoint)`:

1. validates program and checkpoint;
2. creates exact Omega0 `EpochIdentityV1` with:
   - `computation_hash = program_hash`;
   - `input_state_hash = Hash(program_hash, field_hash, pc)`;
   - `authority_hash = program.authority_hash`;
   - exact previous continuation hash;
3. executes at most `quantum_step_limit` instructions;
4. returns `HALTED` if `halt` executes;
5. otherwise returns `SUSPENDED` exactly at the quantum boundary;
6. creates an Omega0 `ContinuationReceiptV1`;
7. returns the next checkpoint whose previous continuation is that exact receipt.

The continuation binds:

```text
result_hash       = Hash(status, field_hash, pc)
state_hash        = Hash(program_hash, field_hash, pc)
observations_hash = Hash([]) for this observation-free profile
effects_hash      = Hash(ordered applied effect-set hashes)
resources_hash    = Hash({steps_used: N})
```

## 6. Open computation theorem target

A program may contain a cycle such as `jump 0`. Therefore the number of epochs is not statically bounded. Nevertheless every call to `run_semantic_quantum` performs no more than `quantum_step_limit` instructions.

The required invariant is:

```text
GLOBAL_PROCESS_MAY_BE_OPEN = true
EVERY_OPERATIONAL_QUANTUM_TERMINATES = true
```

Open duration is represented by an unbounded trace of finite continuation-linked epochs, not by a hidden `while true` inside the runtime.

## 7. Failure

Fail closed before/within the current epoch on:

- malformed/tampered program or checkpoint hashes;
- duplicate transformation hashes;
- invalid PC targets;
- proof-open transformation in this executable profile;
- checkpoint/program mismatch;
- invalid continuation chain;
- transformation applicability failure;
- malformed Omega continuation identity.

No failure finalizes a forged continuation.

## 8. Compatibility

This profile does not reinterpret V2 Program IR V4 and does not modify Omega0 continuation semantics. It consumes the existing Omega0 epoch/continuation API as authority.
