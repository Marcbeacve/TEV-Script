# TEVScript MAX 3.1 Total-Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an additive TEVScript MAX `3.1.0` Total-Core profile that composes exact Program IR V4 child programs with V3 Field/Transformation/Apply/continuation semantics under one canonical Program IR V5 identity, then certify and package it without changing predecessor semantics.

**Architecture:** Program IR V5 Total-Core embeds exact validated V4 units and adds a single `invoke_v4` bridge operation. Child results become immutable canonical Field facts; proof-open transformations require separate externally supplied proof-admission objects. Python and independent JavaScript runtimes must agree on governed vectors. V2, V3 and the `3.0.0` wheel remain immutable predecessors.

**Tech Stack:** Python 3.11+, stdlib-only runtime/package, existing TEVScript V2/V3/V4/V5 modules, Node.js for independent JavaScript parity, pytest/unittest repository suite, deterministic PEP 517 wheel backend.

## Global Constraints

- Base commit: `edd868cf481c358a2b435eb014af8dfee7ab7417`.
- Base tree: `5c17d42967965e4f6ec5316bb84d41a75f141edc`.
- Work branch: `agent/tevscript-max-3-1-total-core-v1`.
- Language/package target: `3.1.0`.
- PyPI project remains `tev-script-portable-reference`.
- Target wheel filename: `tev_script_portable_reference-3.1.0-py3-none-any.whl`.
- Runtime dependencies remain exactly zero.
- `Field + Transformation` remains the primitive semantic basis.
- Existing V2/V3 source, IR schemas, runtimes and `packaging/v3` are not modified to reinterpret predecessor semantics.
- Every V5 operational quantum remains finitely bounded.
- Physical effect commit is never granted by an embedded V4 command plan.
- Proof admission is external explicit evidence; source cannot fabricate it.
- JavaScript Total-Core parity is independent from Python and must implement the governed V4/V5 semantics from normative specs.
- No Stable Admission, tag, PyPI publication or merge is authorized by focal test success alone.

---

### Task 1: Program IR V5 Total-Core canonical model

**Files:**
- Create: `tests/test_program_ir_v5_total.py`
- Create: `tev_script/program_ir_v5_total.py`
- Create: `schemas/tev-script-program-ir-v5-total-core.schema.json`
- Create: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`

**Interfaces:**
- Consumes: `validate_program_ir_v4`, `FieldTransformationV1`, `SemanticFieldV1`, canonical SHA-256 helpers from existing V3 modules.
- Produces: `VerifiedProofAdmissionV1`, `TotalCoreUnitV1`, `TotalCoreInstructionV1`, `TotalCoreProgramV1`, `validate_total_core_program`, `canonical_total_core_program_bytes`.

- [ ] **Step 1: Write RED tests for proof admissions and V4 units**

Create tests that construct a V4 pure artifact with:

```python
compiled = compile_program_v2(
    'script Demo version "2.0.0"; fn f(x:Int)->Int=x+1; entry main:Int=f(4);'
)
ir = export_program_ir_v4_pure(compiled)
unit = TotalCoreUnitV1.build("calc", "pure", ir)
assert unit.program_ir_hash == ir["program_ir_hash"]
```

Add independent negatives for duplicate `unit_id`, duplicate `unit_hash`, profile/schema mismatch, tampered child `program_ir_hash`, invalid relation IDs, duplicate proof requirement and tampered proof admission hash.

- [ ] **Step 2: Run RED tests**

Run:

```powershell
python -m pytest -q tests/test_program_ir_v5_total.py
```

Expected: collection/import failure because `tev_script.program_ir_v5_total` does not yet exist.

- [ ] **Step 3: Implement canonical dataclasses and validation**

Implement exact schemas:

```python
TOTAL_CORE_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1"
TOTAL_UNIT_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_UNIT_V1"
TOTAL_INSTRUCTION_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_INSTRUCTION_V1"
PROOF_ADMISSION_SCHEMA_V1 = "TEV_SCRIPT_PROGRAM_IR_V5_PROOF_ADMISSION_V1"
LANGUAGE_VERSION_V31 = "3.1.0"
PROFILE_TOTAL_CORE = "total_core"
```

`TotalCoreUnitV1.build()` must call `validate_program_ir_v4`, require the declared profile to match the validated V4 schema, retain the exact child mapping and bind `program_ir_hash`. `VerifiedProofAdmissionV1.build()` accepts exactly lowercase 64-hex hashes and `status="VERIFIED"`. `TotalCoreInstructionV1` admits only `apply`, `branch_fact`, `jump`, `halt`, `invoke_v4`; `invoke_v4` requires `(unit_hash, result_relation, next_pc)`.

Program hashing uses canonical JSON of the full program body without `program_hash` and sorts unit/proof/transformation tables by canonical identity.

- [ ] **Step 4: Add JSON schema and normative spec**

Schema must reject unknown fields and encode all five instruction kinds with closed `oneOf` branches. The spec must pin the exact canonical ordering and child-V4 validation rule.

- [ ] **Step 5: Run GREEN and predecessor focal tests**

```powershell
python -m pytest -q tests/test_program_ir_v5_total.py tests/test_program_ir_v4.py tests/test_program_ir_v4_recursive.py tests/test_program_ir_v4_effects.py tests/test_program_ir_v5_semantic.py
```

Expected: all PASS, zero unexpected skips.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_program_ir_v5_total.py tev_script/program_ir_v5_total.py schemas/tev-script-program-ir-v5-total-core.schema.json spec/TEV_SCRIPT_V31_TOTAL_CORE.md
git commit -m "feat(v31): add canonical Total-Core IR"
```

---

### Task 2: Total-Core runtime and canonical V4 result bridge

**Files:**
- Create: `tests/test_runtime_v5_total.py`
- Create: `tev_script/runtime_v5_total.py`

**Interfaces:**
- Consumes: Task 1 types, `run_program_ir_v4_pure`, `run_program_ir_v4_recursive`, `run_program_ir_v4_effects`, `apply_field_transformation`, Omega continuation contracts.
- Produces: `TotalCoreCheckpointV1`, `TotalCoreQuantumResultV1`, `initial_total_core_checkpoint`, `run_total_core_quantum`.

- [ ] **Step 1: Write RED pure/recursive/effects bridge tests**

Each test embeds one exact V4 unit, invokes it once, then halts. Assert that the resulting Field contains one relation selected by `result_relation` and that the fact arguments bind at least `unit_id`, `unit_hash`, `program_ir_hash`, `run_receipt_hash`. Pure/recursive tests additionally assert result encoding/hash; effects test asserts final state hash and capability transcript hash.

- [ ] **Step 2: Write RED continuation/quantum negatives**

Cover checkpoint/program mismatch, previous-continuation mismatch, invalid PC, quantum exhaustion, V4 child failure, and ensure failure emits no forged continuation.

- [ ] **Step 3: Run RED tests**

```powershell
python -m pytest -q tests/test_runtime_v5_total.py
```

Expected: import failure for `runtime_v5_total`.

- [ ] **Step 4: Implement runtime**

Dispatch `invoke_v4` by exact `TotalCoreUnitV1.profile`. Build bridge facts through `FieldFactV1`; persist them by a derived `FieldTransformationV1` so all state change still passes through Apply. The derived transformation identity must bind child `unit_hash` and `run_receipt_hash`. Every instruction consumes one V5 quantum step; separately accumulate child V4 evaluation steps.

- [ ] **Step 5: Bind continuation evidence**

`observations_hash` must bind ordered effects-unit transcript hashes. `effects_hash` must bind ordered Apply effect-set hashes plus available V4 transition/command identities. `resources_hash` binds both V5 instruction steps and total V4 evaluation steps.

- [ ] **Step 6: Run GREEN plus semantic-process non-regression**

```powershell
python -m pytest -q tests/test_runtime_v5_total.py tests/test_runtime_v5_semantic.py tests/test_omega_kernel_v1.py
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add tests/test_runtime_v5_total.py tev_script/runtime_v5_total.py
git commit -m "feat(v31): execute Total-Core quanta"
```

---

### Task 3: External proof-admission execution

**Files:**
- Modify: `tests/test_runtime_v5_total.py`
- Modify: `tev_script/runtime_v5_total.py`

**Interfaces:**
- Consumes: `VerifiedProofAdmissionV1`, transformation `proof_requirement_hashes`.
- Produces: proof-open Apply that succeeds only when every requirement has one exact VERIFIED admission bound to program authority.

- [ ] **Step 1: Add RED proof-open tests**

Create a transformation with a single proof requirement. Assert `PROOF_REQUIRED` or deterministic rejection with no admission. Add one exact admission and assert Apply succeeds. Add authority mismatch, requirement mismatch and tampered admission hash negatives.

- [ ] **Step 2: Run RED test nodeids**

```powershell
python -m pytest -q tests/test_runtime_v5_total.py -k proof
```

Expected: failures because proof-open execution is still rejected.

- [ ] **Step 3: Implement proof resolver**

Build a map keyed by `requirement_hash`. Require exact `program.authority_hash`; reject duplicates. Strip requirements only in a derived execution-local transformation after successful admission validation; retain original transformation hash plus ordered admission hashes in the derived execution/receipt evidence. Never mutate the canonical program transformation.

- [ ] **Step 4: Run GREEN and V3 proof-required non-regression**

```powershell
python -m pytest -q tests/test_runtime_v5_total.py tests/test_omega_semantic_basis_v1.py tests/test_program_ir_v5_semantic.py
```

Expected: PASS; V3 semantic-process remains proof-closed.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_runtime_v5_total.py tev_script/runtime_v5_total.py
git commit -m "feat(v31): admit externally verified proof requirements"
```

---

### Task 4: Unified 3.1 source compiler

**Files:**
- Create: `tests/test_source_total_core_v31.py`
- Create: `tev_script/source_total_core_v31.py`

**Interfaces:**
- Consumes: V3 fact/field/transform parsing rules, `compile_program_v2`, `export_program_ir_v4_pure`, `export_program_ir_v4_recursive`, V2 effects source exporter/Program IR V4 effects builder, Task 1 Total-Core builders.
- Produces: `SourceTotalCoreV31`, `compile_total_core_v31(process_source, *, unit_sources, proof_admissions=())`.

- [ ] **Step 1: Write RED source tests**

Use process source:

```text
process Demo version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field default = [];
label Start = invoke_v4 Calc result tev.total.result End;
label End = halt;
entry Start;
```

and `unit_sources={"Calc": 'script Calc version "2.0.0"; fn f(x:Int)->Int=x+1; entry main:Int=f(4);'}`. Assert deterministic compile under mapping order/path changes and exact child `program_ir_hash` binding.

Negatives: extra/missing unit source, duplicate unit declaration, unsupported version, profile mismatch, V2 child not `2.0.0`, source text attempting a `proof_admission` declaration.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest -q tests/test_source_total_core_v31.py
```

Expected: import failure.

- [ ] **Step 3: Implement parser as additive V3.1 process parser**

Reuse strict canonical JSON/relation validators; do not modify V3 parser. Resolve labels lexically and unit names symbolically. Build canonical source model and `source_semantic_hash` from process model + sorted child `(unit_id, child_semantic_hash, program_ir_hash)`.

- [ ] **Step 4: Implement exact V2 child lowering**

Pure/recursive profiles compile through `compile_program_v2` then corresponding V4 exporter. Effects profile must call the existing V2 effect-source authority rather than synthesizing ad-hoc V4 objects; if the existing source API does not expose a detached V4 artifact, add the smallest adapter in this new V3.1 module without modifying V2 semantics.

- [ ] **Step 5: Run GREEN plus V2/V3 source tests**

```powershell
python -m pytest -q tests/test_source_total_core_v31.py tests/test_source_program_v2.py tests/test_source_effect_program_v2.py tests/test_source_semantic_process_v3.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_source_total_core_v31.py tev_script/source_total_core_v31.py
git commit -m "feat(v31): compile unified Total-Core projects"
```

---

### Task 5: CLI, descriptor, schemas and public API

**Files:**
- Create: `tests/test_cli_v31.py`
- Create: `tests/test_v31_descriptor.py`
- Create: `tev_script/cli_v31.py`
- Create: `tev_script/descriptor_v31.py`
- Create: `tev_script/describe_v31.py`
- Create: `schemas/tev-script-v31-descriptor.schema.json`
- Modify: `tev_script/__init__.py` only for additive 3.1 exports.

**Interfaces:**
- Produces installed/module CLIs and descriptor.

- [ ] **Step 1: Write RED descriptor/API/CLI tests**

Descriptor must report `language_version=3.1.0`, `program_ir_version=5`, `profiles=["total_core"]`, predecessor V3 `3.0.0`, `v2_units_embedded_without_reinterpretation=true`, `proof_admission_external_only=true`, `physical_effect_commit_inside_runtime=false`.

- [ ] **Step 2: Run RED**

```powershell
python -m pytest -q tests/test_cli_v31.py tests/test_v31_descriptor.py
```

- [ ] **Step 3: Implement descriptor and CLI using shared Task 1-4 APIs**

Commands: `descriptor`, `compile-total`, `validate-total`, `run-total`, `resume-total`. No command implements independent semantic logic.

- [ ] **Step 4: Run GREEN plus V3 CLI regression**

```powershell
python -m pytest -q tests/test_cli_v31.py tests/test_v31_descriptor.py tests/test_cli_v3.py tests/test_v3_descriptor_runtime_targets.py
```

- [ ] **Step 5: Commit**

```powershell
git add tests/test_cli_v31.py tests/test_v31_descriptor.py tev_script/cli_v31.py tev_script/descriptor_v31.py tev_script/describe_v31.py schemas/tev-script-v31-descriptor.schema.json tev_script/__init__.py
git commit -m "feat(v31): expose Total-Core CLI and descriptor"
```

---

### Task 6: Independent JavaScript Total-Core runtime

**Files:**
- Create: `runtime_js_v31/runtime_v5_total.mjs`
- Create: `tests/test_runtime_v5_total_js_parity.py`
- Create: `conformance/v31-total-core-parity.json`

**Interfaces:**
- Consumes normative V4/V5 schemas/vectors only; no Python runtime delegation.
- Produces JSON-in/JSON-out validator/runtime used by parity tests.

- [ ] **Step 1: Add RED cross-runtime vectors**

At least one vector each for pure, recursive and effects V4 child profiles, plus tampered unit/proof/checkpoint vectors. Python produces the expected canonical outputs; Node must reproduce exact JSON/hash identities.

- [ ] **Step 2: Run RED with Node**

```powershell
python -m pytest -q tests/test_runtime_v5_total_js_parity.py
```

Expected: FAIL because `runtime_js_v31/runtime_v5_total.mjs` is absent.

- [ ] **Step 3: Implement independent canonical validation and five V5 instructions in JS**

Implement canonical JSON/SHA-256, V4 child validation/execution for the governed pure/recursive/effects profiles directly from normative V4 contracts, Field/Transformation Apply, bridge-fact construction, checkpoint/continuation hashing. Do not spawn Python.

- [ ] **Step 4: Add authority negative proving no Python delegation**

Static test rejects `child_process`, `python`, `python3`, `py.exe` and network/runtime-source compilation references from the JS runtime source.

- [ ] **Step 5: Run GREEN parity**

```powershell
python -m pytest -q tests/test_runtime_v5_total_js_parity.py tests/test_runtime_v5_js_parity.py
```

Expected: PASS, zero skips.

- [ ] **Step 6: Commit**

```powershell
git add runtime_js_v31/runtime_v5_total.mjs tests/test_runtime_v5_total_js_parity.py conformance/v31-total-core-parity.json
git commit -m "feat(v31): add independent JavaScript Total-Core runtime"
```

---

### Task 7: V3.1 feature matrix, authority and focal certification

**Files:**
- Create: `spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json`
- Create: `tests/test_v31_authority.py`
- Create: `tests/test_v31_certify_full.py`
- Create: `schemas/tev-script-v31-certify-full-receipt.schema.json`
- Create: `RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py`

**Interfaces:**
- Produces one exact candidate certification receipt with no release authority.

- [ ] **Step 1: Write RED authority tests**

Require all governed paths, predecessor pins, zero-skip focal gates, V2/V3 unchanged-file hashes, minimality gate, Python/JS parity and candidate publication/merge flags false.

- [ ] **Step 2: Implement feature matrix and certifier**

The certifier must execute exact focal node sets and predecessor V2/V3 gates; it must bind HEAD/TREE, governed-path hashes, test counts, Python/Node versions and all prerequisite receipt hashes. `publication_authorized=false`, `merge_authorized=false` on technical certification.

- [ ] **Step 3: Run focal certifier**

```powershell
python RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py
```

Expected only after prior tasks: `V31_CERTIFY_FULL=PASS`, zero unexpected skips, receipt emitted outside/under governed evidence location consistent with predecessor practice.

- [ ] **Step 4: Commit**

```powershell
git add spec/TEV_SCRIPT_V31_FEATURE_MATRIX.json tests/test_v31_authority.py tests/test_v31_certify_full.py schemas/tev-script-v31-certify-full-receipt.schema.json RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py
git commit -m "feat(v31): add Total-Core certification gate"
```

---

### Task 8: Deterministic `3.1.0` wheel

**Files:**
- Create: `packaging/v31/pyproject.toml`
- Create: `packaging/v31/tools/tev_script_build_backend_v31.py`
- Create: `tests/test_v31_packaging.py`

**Interfaces:**
- Produces `tev_script_portable_reference-3.1.0-py3-none-any.whl` with zero runtime dependencies.

- [ ] **Step 1: Write RED packaging tests**

Assert dedicated packaging authority is `packaging/v31`, version exactly `3.1.0`, required CLIs include V0/V1/V2/V3/V31 surfaces, build backend requires `SOURCE_DATE_EPOCH`, includes Python package `.py` files only, and two builds are byte-identical.

- [ ] **Step 2: Implement packaging by adapting V3 deterministic backend**

Use `BACKEND_SCHEMA="TEV_SCRIPT_PYTHON_WHEEL_BACKEND_V31"`; do not modify `packaging/v3`.

- [ ] **Step 3: Run package tests and isolated install**

```powershell
python -m pytest -q tests/test_v31_packaging.py tests/test_v3_packaging.py
python -m pip wheel .\packaging\v31 --no-deps --no-build-isolation -w .\dist-v31
```

Create a fresh venv, install only the wheel, run `pip check`, invoke `tev-script-v31-describe` and one Total-Core compile/run vector from outside the repository checkout.

- [ ] **Step 4: Commit**

```powershell
git add packaging/v31 tests/test_v31_packaging.py
git commit -m "build(v31): add deterministic Total-Core wheel"
```

---

### Task 9: Full regression, Stable Admission and release-shaped identity

**Files:**
- Create: `schemas/tev-script-v31-stable-admission-receipt.schema.json`
- Create: `tests/test_v31_stable_admission.py`
- Create: `RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py`
- Modify release/index documentation only after the technical candidate is frozen.

**Interfaces:**
- Consumes exact Task 7 technical receipt and Task 8 wheel identity.
- Produces stable-admission receipt for one frozen exact release commit/tree; no merge occurs automatically.

- [ ] **Step 1: Run full repository regression on frozen technical candidate**

```powershell
python -m pytest -q
```

Required: every predecessor and V31 test PASS, zero unexpected skips. Record exact count rather than assuming the predecessor `1335` count.

- [ ] **Step 2: Run V1/V2/V3 governed certification non-regressions**

```powershell
python RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py
python RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py
python RUN_TEV_SCRIPT_V3_CERTIFY_FULL.py
python RUN_TEV_SCRIPT_V31_CERTIFY_FULL.py
```

All required predecessor gates PASS on the exact candidate according to their stable/non-regression profiles.

- [ ] **Step 3: Freeze release-shaped commit**

Only release metadata/index/changelog/version surfaces allowed by the V31 Stable Admission whitelist may change after technical certification. Rebuild the wheel twice from the exact release-shaped source with the pinned `SOURCE_DATE_EPOCH`; byte hashes must match.

- [ ] **Step 4: Run Stable Admission**

```powershell
python RUN_TEV_SCRIPT_V31_STABLE_ADMISSION.py
```

Receipt must bind exact technical parent, exact release HEAD/TREE, full test count, zero skips, predecessor stable identities and exact wheel SHA. Only this gate may emit `V31_LANGUAGE_STABLE=YES` / publication eligibility.

- [ ] **Step 5: Push candidate branch and open/update draft PR**

PR targets `main` but remains draft unless the operator separately authorizes promotion/merge. The PR body records exact identities and explicitly says normal merge/squash/rebase must not replace a stable-admitted identity if fast-forward identity preservation is required.

---

### Task 10: PyPI update and public byte-identity closure

**Files:**
- External publication receipt generated outside the certified source tree.
- After successful publication, update `docs/releases/PYPI_WHEEL_REGISTRY_V1.md` on a separate documentation branch/PR.

**Interfaces:**
- Publishes to existing project `tev-script-portable-reference`, version `3.1.0`; never overwrites `3.0.0`.

- [ ] **Step 1: Twine/check gate on exact admitted wheel**

```powershell
python -m twine check .\dist-v31\tev_script_portable_reference-3.1.0-py3-none-any.whl
```

- [ ] **Step 2: Upload exact certified wheel only with local PyPI token**

Use `TWINE_USERNAME=__token__` and a process-local token captured from clipboard; token must never be printed, committed or pasted into chat.

- [ ] **Step 3: Redownload from public PyPI simple index**

```powershell
python -m pip download --no-cache-dir --no-deps --only-binary=:all: --index-url https://pypi.org/simple --dest .\pypi-verify "tev-script-portable-reference==3.1.0"
```

Assert filename and SHA-256 equal the Stable Admission wheel exactly.

- [ ] **Step 4: Emit independent publication receipt**

Bind project/version/tag/release commit/tree/wheel SHA, Stable Admission receipt hash, PyPI redownload byte identity, `stable_release=true`, and `merge_performed=false` unless an independent merge/promotion operation has actually occurred.

- [ ] **Step 5: Document new wheel without mutating release identity**

Update the wheel registry on a docs-only branch with both retained `3.0.0` historical identity and new `3.1.0` identity. Do not delete or rewrite the 3.0 entry.

---

## Plan self-review

- Spec coverage: Tasks 1-10 cover IR, bridge runtime, proof admission, source, CLI/descriptor, independent JS parity, governance, packaging, Stable Admission and PyPI byte closure.
- Compatibility: no task modifies V2/V3 semantics or `packaging/v3`.
- Type consistency: `TotalCoreUnitV1`, `TotalCoreInstructionV1`, `TotalCoreProgramV1`, `TotalCoreCheckpointV1`, `VerifiedProofAdmissionV1` and `run_total_core_quantum` are introduced before consumers.
- No release step assumes a fixed final regression count; it records the observed count.
- JavaScript ambiguity is closed by the normative amendment: no Python delegation and no assumed pre-existing V4 JS runtime.
- Publication uses the same PyPI project with a new immutable version `3.1.0`.
