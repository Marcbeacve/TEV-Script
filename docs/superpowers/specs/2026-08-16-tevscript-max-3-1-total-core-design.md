# TEVScript MAX 3.1 Total-Core — Design

Date: 2026-08-16
Status: APPROVED DESIGN / IMPLEMENTATION AUTHORIZED BY OPERATOR
Base: `main=edd868cf481c358a2b435eb014af8dfee7ab7417`
Base tree: `5c17d42967965e4f6ec5316bb84d41a75f141edc`
Stable predecessor: `TEVScript MAX 3.0.0`, tag `v3.0.0`
Canonical predecessor wheel: `tev_script_portable_reference-3.0.0-py3-none-any.whl`
Canonical predecessor wheel SHA-256: `800cab8a9390a44b281fb49a52f796127fa4e6cd2b21043718603899f1137707`
Target language/package version: `3.1.0`
Target PyPI project: `tev-script-portable-reference`

## 1. Objective

TEVScript MAX 3.1 closes the first **Total-Core** profile of Program IR V5. The goal is not to add a second general-purpose kernel. The goal is to compose the already-certified computational power of Program IR V4 with the already-certified MAX semantic basis `Field + Transformation + Apply + bounded quantum + continuation` under one content-addressed Program IR V5 program identity.

The target relation is:

```text
V2 finite computation / state / observation / command planning
                     +
V3 Field / Transformation / Apply / Omega continuation
                     ↓
          Program IR V5 Total-Core
```

V2 and V3 remain independently valid compatibility authorities. 3.1 is additive and must not reinterpret either predecessor.

## 2. Hard invariants

1. `v3.0.0`, commit `edd868cf...`, tree `5c17d429...` and its wheel bytes are immutable predecessor authority.
2. No V2 or V3 artifact acquires 3.1 semantics by being loaded by a 3.1 runtime.
3. Every V4 child artifact embedded in Total-Core retains its exact `program_ir_hash` and is validated by the existing V4 validator for its declared schema.
4. `Field + Transformation` remains the semantic primitive basis. V4 units, collections, generics, protocols, tasks and domain concepts are derived computational structures, not new primitive semantic families.
5. Every operational quantum terminates at the declared finite quantum bound.
6. Global computation may remain open only through continuation-linked finite quanta.
7. No source declaration, embedded effect set or V4 command plan grants physical authority.
8. Physical commit remains an explicit provider/grant operation outside pure Program IR execution.
9. Proof requirements are never silently treated as satisfied.
10. Python, JavaScript or any later runtime is an implementation target, not language authority.

## 3. Why Total-Core reuses V4 instead of copying V2

Program IR V4 already closes finite collections, user generics, associated protocols/types, contracted recursion, pure task DAGs, deterministic observations, effect command planning and bounded state transitions. Reimplementing those semantics inside V5 would create two independently evolving copies of the same language and enlarge the trusted semantic base without a counterexample requiring it.

Total-Core therefore embeds **validated V4 units** as closed content-addressed child programs and gives V5 a minimal invocation bridge. V5 owns composition, Field semantics, proof admission, continuation identity and cross-unit receipt binding. V4 continues to own the exact computation of a V4 unit.

## 4. Program IR V5 Total-Core

New module: `tev_script/program_ir_v5_total.py`.

Canonical schemas:

```text
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_INSTRUCTION_V1
TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CHECKPOINT_V1
TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1
```

Program discriminator:

```text
language_version = 3.1.0
profile          = total_core
```

A Total-Core program binds:

```text
program_id
source_semantic_hash
initial_field
transformations[]
v4_units[]
proof_admissions[]
instructions[]
entry_pc
quantum_step_limit
authority_hash
program_hash
```

### 4.1 V4 unit

A unit is:

```text
unit_id
profile = pure | recursive | effects
program_ir_v4
program_ir_hash
unit_hash
```

Rules:

- `program_ir_v4` is the exact canonical V4 mapping;
- its schema must match `profile`;
- validation delegates to the existing corresponding V4 validator;
- `program_ir_hash` must equal the hash reconstructed by that validator;
- `unit_hash = Hash(schema, unit_id, profile, program_ir_hash)`;
- unit IDs and unit hashes are unique;
- runtime never compiles source inside a unit.

### 4.2 Instruction set

Total-Core inherits the closed semantic-process operations and adds exactly one computational bridge:

```text
apply
branch_fact
jump
halt
invoke_v4
```

`invoke_v4` contains:

```text
unit_hash
result_relation
next_pc
```

`result_relation` is a stable relation identifier selected at compile time. Runtime executes the exact child unit and appends one canonical bridge fact to the Field. The bridge fact arguments are profile-specific but always include:

```text
unit_id
unit_hash
program_ir_hash
run_receipt_hash
```

For `pure` and `recursive`, the fact additionally binds:

```text
result_type
result_encoded
result_hash
evaluation_steps
```

For `effects`, it additionally binds:

```text
final_state
final_state_hash
capability_transcript_hash
evaluation_steps
observation_calls
```

This is a one-way explicit bridge from a validated computational result into Field data. It does not mutate the child unit and does not grant an effect.

## 5. Proof admission

V3 semantic-process V1 correctly rejects proof-open transformations. 3.1 adds a separate **externally supplied proof-admission object**; source code cannot manufacture one by writing a declaration.

A proof admission binds:

```text
requirement_hash
verification_receipt_hash
verifier_identity_hash
authority_hash
status = VERIFIED
admission_hash
```

Rules:

- all hashes are lowercase SHA-256 identities;
- the admission is content-addressed and program-bound;
- source compilation receives admissions as a separate explicit input;
- every `proof_requirement_hash` on an applied transformation must have one exact admission with matching `requirement_hash` and program `authority_hash`;
- absence produces deterministic `PROOF_REQUIRED`, never PASS;
- the Total-Core runtime validates admission integrity but does not claim to re-prove the external theorem; the verifier identity and verification receipt remain visible evidence.

## 6. Total-Core runtime

New module: `tev_script/runtime_v5_total.py`.

Primary API:

```python
run_total_core_quantum(
    program: TotalCoreProgramV1,
    checkpoint: TotalCoreCheckpointV1,
    *,
    task_strategy: TaskScopeExecutionStrategyV4 | None = None,
) -> TotalCoreQuantumResultV1
```

Execution rules:

- validate full program and checkpoint before the first instruction;
- `apply` uses the existing Field/Transformation calculus; proof-open Apply is admitted only by the exact proof-admission table;
- `invoke_v4` dispatches only by the embedded V4 schema/profile to `run_program_ir_v4_pure`, `run_program_ir_v4_recursive` or `run_program_ir_v4_effects`;
- the V4 receipt is converted to one canonical bridge fact and added by a derived Field transformation whose identity binds the unit and receipt;
- `branch_fact`, `jump` and `halt` retain V3 semantics;
- every instruction consumes one V5 quantum step; V4 receipt resource counts are separately accumulated and cannot change the V5 instruction bound;
- continuation `observations_hash` binds ordered V4 effects-profile transcript hashes;
- continuation `effects_hash` binds ordered Apply effect-set hashes plus V4 effects-profile command/transition receipt identities where available;
- continuation `resources_hash` binds V5 steps plus child V4 evaluation-step totals;
- a failed V4 invocation or malformed proof admission fails the current quantum closed and emits no forged continuation.

Checkpoint state remains only:

```text
program_hash
field
pc
next_epoch_index
previous_continuation
halted
checkpoint_hash
```

V4 results are persisted only through canonical bridge facts, so no hidden runtime state is introduced.

## 7. Source profile 3.1

New module: `tev_script/source_total_core_v31.py`.

3.1 is a **project-level unified source profile** rather than a textual copy of the V2 grammar. It consists of one 3.1 process source plus a finite explicit mapping of named V2 source units.

The 3.1 process syntax is additive over V3 semantic-process source:

```text
process <ProgramId> version "3.1.0";
authority <sha256>;
quantum_steps <N>;

unit <UnitName> profile pure|recursive|effects;

fact ...;
field ...;
transform ...;

label <L> = invoke_v4 <UnitName> result <relation-id> <NextLabel>;
label <L> = apply ...;
label <L> = branch_fact ...;
label <L> = jump ...;
label <L> = halt;

entry <Label>;
```

Compilation API:

```python
compile_total_core_v31(
    process_source: str,
    *,
    unit_sources: Mapping[str, str],
    proof_admissions: Sequence[VerifiedProofAdmissionV1] = (),
) -> TotalCoreProgramV1
```

For every declared unit:

1. the logical unit name must exist exactly once in `unit_sources`;
2. the child source must be a V2 `2.0.0` source program;
3. it is compiled through existing V2 source/compiler authority;
4. the declared profile selects the corresponding canonical V4 exporter;
5. the resulting V4 artifact is embedded without reinterpretation;
6. source paths and mapping enumeration order are nonsemantic;
7. extra undeclared `unit_sources` entries are rejected.

The Total-Core `source_semantic_hash` binds the canonical 3.1 process model plus each child unit's V2 semantic hash and V4 `program_ir_hash`, sorted by logical unit ID.

This closes one language-level 3.1 program identity without copying V2 syntax into a second parser.

## 8. Native state, observations and effect-command semantics

3.1 considers these capabilities native to Total-Core because a Total-Core program can embed and invoke V4 `effects` units under the same V5 `program_hash`, continuation chain and Field state.

This does **not** mean physical commands commit inside the portable runtime. The existing V2 separation remains normative:

```text
observation transcript -> deterministic computation -> inert command intent
                                               ↓
                                external exact grant/provider
                                               ↓
                                      physical commit
```

Total-Core records and transports the resulting deterministic artifacts and receipts. Provider commit remains outside the pure portable runtime.

## 9. CLI and descriptor

New additive entry points:

```text
tev-script-v31
tev-script-v31-describe
python -m tev_script.cli_v31
python -m tev_script.describe_v31
```

Existing V0/V1/V2/V3 CLIs are unchanged.

`tev-script-v31` exposes at least:

```text
descriptor
compile-total
run-total
resume-total
validate-total
```

CLI and Python APIs call the same compiler/validator/runtime functions.

New descriptor schema: `schemas/tev-script-v31-descriptor.schema.json`.

The descriptor must report:

```text
language_version = 3.1.0
program_ir_version = 5
profiles = [total_core]
predecessor_v3 = 3.0.0
v2_units_embedded_without_reinterpretation = true
proof_admission_external_only = true
physical_effect_commit_inside_runtime = false
```

## 10. Independent runtime parity

Python is the reference implementation but not sole authority. Add an independent JavaScript Total-Core runtime under `runtime_js_v31/`.

The JS runtime must:

- validate the same Total-Core canonical artifact;
- implement the same five instruction kinds;
- reproduce V4 child execution for the governed Total-Core conformance subset using existing JS V4/V2 semantics where present;
- reproduce bridge facts, Field hashes, continuation hashes and quantum hashes byte-for-byte;
- reject tampered program/unit/proof/checkpoint identities identically.

No Stable Admission can pass while JS parity is skipped.

## 11. Packaging 3.1

New isolated packaging surface:

```text
packaging/v31/pyproject.toml
packaging/v31/tools/tev_script_build_backend_v31.py
```

Metadata:

```text
project.name = tev-script-portable-reference
project.version = 3.1.0
requires-python = >=3.11
dependencies = []
```

Expected wheel:

```text
tev_script_portable_reference-3.1.0-py3-none-any.whl
```

The deterministic backend remains stdlib-only and requires `SOURCE_DATE_EPOCH`. Two clean builds from the exact release tree must be byte-identical. The published PyPI wheel must be downloaded back and match the certified SHA-256 exactly.

PyPI `3.0.0` is never replaced.

## 12. Governance and certification

New governed files:

```text
spec/TEV_SCRIPT_V31_TOTAL_CORE.md
spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json
schemas/tev-script-program-ir-v5-total-core.schema.json
schemas/tev-script-v31-descriptor.schema.json
schemas/tev-script-v31-certify-full-receipt.schema.json
schemas/tev-script-v31-stable-admission-receipt.schema.json
tev_script/program_ir_v5_total.py
tev_script/runtime_v5_total.py
tev_script/source_total_core_v31.py
tev_script/cli_v31.py
tev_script/descriptor_v31.py
tev_script/describe_v31.py
runtime_js_v31/*
packaging/v31/*
RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py
RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py
```

Stable Admission requires exact predecessor identity plus all 3.1 gates.

## 13. Required positive gates

```text
TOTAL_CORE_IR_V5=PASS
TOTAL_CORE_SOURCE=PASS
V4_PURE_UNIT_PARITY=PASS
V4_RECURSIVE_UNIT_PARITY=PASS
V4_EFFECTS_UNIT_PARITY=PASS
V2_COLLECTION_PARITY=PASS
V2_GENERIC_PARITY=PASS
V2_PROTOCOL_PARITY=PASS
V2_TASK_PARITY=PASS
NATIVE_V5_STATE=PASS
NATIVE_V5_OBSERVATIONS=PASS
NATIVE_V5_EFFECT_COMMANDS=PASS
PROOF_ADMISSION=PASS
FIELD_TRANSFORMATION_MINIMALITY_PRESERVED=PASS
EVERY_OPERATIONAL_QUANTUM_TERMINATES=PASS
GLOBAL_PROCESS_MAY_BE_OPEN=PASS
PYTHON_RUNTIME_PARITY=PASS
JAVASCRIPT_RUNTIME_PARITY=PASS
V3_0_NONREGRESSION=PASS
V2_NONREGRESSION=PASS
FULL_REPOSITORY_REGRESSION=PASS
ZERO_SKIP=PASS
V31_PACKAGE_REPRODUCIBLE=PASS
V31_STABLE_ADMISSION=PASS
```

## 14. Required negatives

At minimum, independent tests must reject:

- duplicate unit ID;
- duplicate unit hash;
- V4 unit profile/schema mismatch;
- tampered embedded `program_ir_hash`;
- unknown `invoke_v4` unit;
- invalid bridge relation;
- extra or missing `unit_sources` entry;
- V2 child with language version other than `2.0.0`;
- proof-open Apply without admission;
- proof admission requirement mismatch;
- proof admission authority mismatch;
- proof admission hash tamper;
- source attempting to manufacture proof admission;
- V4 invocation failure being converted to PASS;
- child receipt omitted from bridge fact;
- child receipt omitted from continuation evidence;
- checkpoint/program mismatch;
- continuation predecessor mismatch;
- V5 target PC out of range;
- quantum step overflow;
- physical-effect authority inferred from a V4 command plan;
- 3.0 semantic-process artifact accepted as `total_core`;
- V2 artifact silently rewritten as 3.1 source.

## 15. Compatibility guarantees

- Existing `semantic_process` schema remains exactly `TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1` with language version `3.0.0`.
- Existing `run_semantic_quantum` behavior is unchanged.
- Existing V2 Program IR V4 schemas and validators are unchanged.
- Existing V3 `packaging/v3` remains the authority for wheel `3.0.0`.
- 3.1 uses `packaging/v31`; no root package metadata is treated as 3.1 release authority.

## 16. Release identity

Only after Stable Admission PASS:

```text
repository release = 3.1.0
tag = v3.1.0
PyPI project = tev-script-portable-reference
PyPI version = 3.1.0
wheel = tev_script_portable_reference-3.1.0-py3-none-any.whl
```

The release receipt must bind exact commit, exact tree, all predecessor identities, wheel SHA-256, full-regression count, zero-skip result and PyPI redownload byte identity.

## 17. Definition of Done

TEVScript MAX 3.1 Total-Core is complete only when:

1. Total-Core source compiles to one canonical V5 program identity;
2. V4 pure/recursive/effects units execute under that program without semantic copying;
3. their results enter Field only through canonical bridge facts;
4. proof-open transformations require external verified admissions;
5. open computation remains a chain of bounded quanta;
6. Python and independent JavaScript runtimes agree byte-for-byte on governed vectors;
7. all V2 and V3 predecessor regressions pass with zero unexpected skips;
8. two clean `3.1.0` wheel builds are byte-identical;
9. Stable Admission passes on the exact frozen release identity;
10. the exact certified wheel is published under the existing PyPI project as version `3.1.0` and redownloaded with identical SHA-256;
11. no merge or publication is performed solely because implementation tests pass; release authority comes from the explicit Stable Admission receipt and operator authorization.
