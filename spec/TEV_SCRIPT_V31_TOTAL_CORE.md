# TEVScript 3.1 Total-Core — Normative Program IR V5 Profile

Status: candidate specification for `3.1.0`.

## 1. Identity

The only Program IR V5 Total-Core root schema is:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
```

with the fixed discriminators:

```text
language_version = 3.1.0
profile          = total_core
```

The canonical root fields are:

```text
schema
language_version
profile
program_id
source_semantic_hash
initial_field
transformations
v4_units
proof_admissions
instructions
entry_pc
quantum_step_limit
authority_hash
program_hash
```

`program_hash` is SHA-256 over canonical JSON of the full root body with `program_hash` omitted.

## 2. Additive predecessor rule

Total-Core is additive. It does not reinterpret TEVScript V2 source, Program IR V4, or TEVScript MAX 3.0 semantic-process artifacts.

A 3.0 semantic-process artifact remains identified by:

```text
TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1
language_version = 3.0.0
profile = semantic_process
```

and MUST NOT be accepted as Total-Core.

## 3. V4 child units

A child unit has schema:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1
```

and fields:

```text
unit_id
profile = pure | recursive | effects
program_ir_v4
program_ir_hash
unit_hash
```

The embedded `program_ir_v4` mapping is detached canonical JSON data. Its declared `program_ir_hash` MUST be validated by the existing Program IR V4 validator corresponding to the declared profile. The V5 validator MUST NOT reimplement or reinterpret the V4 computation.

Profile/schema correspondence is exact:

```text
pure      -> TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1
recursive -> TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1
effects   -> TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1
```

`unit_hash` is SHA-256 over canonical JSON of:

```json
{
  "schema": "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1",
  "unit_id": "<stable-id>",
  "profile": "<profile>",
  "program_ir_hash": "<sha256>"
}
```

Unit IDs and unit hashes are unique within one Total-Core program. Canonical unit order is `(unit_id, unit_hash)` ascending.

## 4. Primitive semantic basis

Total-Core does not introduce a new semantic primitive family. The primitive semantic basis remains:

```text
Field + Transformation
```

with `Apply` as the operational judgment. V4 units are derived, closed computational child artifacts.

Transformations are ordered by `transformation_hash` ascending.

## 5. Proof admissions

A proof admission has schema:

```text
TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1
```

and binds:

```text
requirement_hash
verification_receipt_hash
verifier_identity_hash
authority_hash
status = VERIFIED
admission_hash
```

All identities are lowercase 64-hex SHA-256 strings. `admission_hash` covers all fields except itself.

Within one program:

- `requirement_hash` is unique;
- `admission_hash` is unique;
- every admission `authority_hash` equals the program `authority_hash`.

A transformation with proof requirements is structurally admissible only when every requirement has one exact admission. This does not allow source text to manufacture verification authority; proof admissions are externally supplied evidence.

Canonical proof order is `(requirement_hash, admission_hash)` ascending.

## 6. Instruction set

The only Total-Core instruction kinds are:

```text
apply
branch_fact
jump
halt
invoke_v4
```

Every instruction is content-addressed by `instruction_hash` over its complete canonical instruction body.

`invoke_v4` contains exactly:

```text
unit_hash
result_relation
next_pc
```

All unrelated instruction fields are canonically `null`.

`result_relation` is a stable relation identifier. `unit_hash` MUST identify one exact embedded unit. All PC targets MUST be within the instruction table.

Instruction table order is source/control-flow order and is therefore semantic; it is never sorted.

## 7. Program ordering and bounds

Canonical table ordering is:

```text
transformations  by transformation_hash
v4_units         by (unit_id, unit_hash)
proof_admissions by (requirement_hash, admission_hash)
instructions     preserved control-flow order
```

Bounds:

```text
1 <= instruction_count <= 65536
1 <= quantum_step_limit <= 1000000
0 <= entry_pc < instruction_count
```

Every runtime quantum MUST consume at most `quantum_step_limit` V5 instructions. Open global execution is represented only by explicit continuation-linked finite quanta.

## 8. Runtime bridge contract

`invoke_v4` executes the exact embedded V4 child using its corresponding existing V4 runtime. A successful child result is projected into one immutable Field fact using `result_relation`.

Every bridge fact MUST bind at least:

```text
unit_id
unit_hash
program_ir_hash
run_receipt_hash
```

Pure and recursive bridges additionally bind their result type, encoded result, result hash and evaluation-step count. Effects bridges additionally bind final state, final-state hash, capability transcript hash, evaluation steps and observation-call count.

The Field mutation that adds a bridge fact MUST itself be expressed through a derived Field transformation and Apply; the runtime must not mutate Field storage out-of-band.

## 9. Effect authority boundary

An embedded V4 effects unit may deterministically compute observations, state transitions and command intent according to existing V4 semantics. It does not thereby gain physical effect authority.

Physical commit remains outside portable Total-Core execution and requires the existing explicit provider/grant boundary. A V4 command plan is evidence or intent, never an ambient capability grant.

## 10. Canonical serialization

Canonical bytes are UTF-8 bytes of TEVScript canonical JSON. Unknown V5 root/unit/proof/instruction fields are rejected. Embedded V4 mappings are validated by their exact V4 validators, which remain their semantic authority.

## 11. Compatibility

TEVScript 3.1 MUST preserve:

- Program IR V4 validators and execution semantics;
- Program IR V5 semantic-process 3.0 behavior;
- MAX 3.0 Field/Transformation identities;
- the published `tev-script-portable-reference==3.0.0` artifact as immutable predecessor evidence.

No focal Total-Core PASS grants Stable Admission, tag, publication or merge authority.
