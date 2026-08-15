# TEV-Script Ω0 Kernel Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a minimal canonical `K/P/C/R/E` contract layer that projects existing stable V2 artifacts into Ω identities, authority/resource/effect evidence, and continuation receipts without changing V2 semantics or grammar.

**Architecture:** Ω0 is additive. `tev_script/omega_kernel_v1.py` contains small canonical data models and validators only; `tev_script/omega_v2_adapter_v1.py` is the sole bridge from validated V2 Program IR/receipts into those models. `tools/tevprober_omega0.py` seals the exact additive frontier and has no promotion authority. `RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py` runs Ω0 tests plus V2 non-regression and emits an external self-hashed technical receipt with `LANGUAGE_STABLE=NO`.

**Tech Stack:** Python 3.11+ standard library, existing `tev_script.canonical`, existing V2 Program IR validators/runners, `unittest`, canonical SHA-256, external JSON receipts. No new runtime dependency. No GitHub Actions.

## Global Constraints

- Exact stable base: `2bdb047dcad41f9d112219bd65925c25668c02e0`.
- Exact stable base tree: `aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8`.
- V2 stable receipt remains `4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6` and is never rewritten.
- Branch: `agent/tev-script-omega-kernel-v1`.
- Ω0 does not change V2 grammar, static semantics, Program IR V4 schemas, value semantics, V2 release metadata, V2 canonical index, V2 feature matrix, stable-admission tooling, or any existing V2 runtime implementation file.
- Ω0 artifacts are research/candidate evidence only and must never emit `LANGUAGE_STABLE=YES`.
- External AI/prover/compiler assertions are never trusted directly.
- Unknown resource information is represented explicitly; it is never interpreted as zero.
- Authority/effect/resource/proof/hash mismatches fail closed.
- Existing V2 Program IR is validated by existing V2 validators before Ω projection.
- No ambient I/O or physical effect is introduced by Ω0.
- No merge, release, tag, stable promotion, or `main` mutation without explicit authorization.

---

## File map

**Create:**
- `tev_script/omega_kernel_v1.py` — canonical Ω0 K/P/C/R/E data models, canonical serializers, hashes, validators, resource/effect algebra primitives.
- `tev_script/omega_v2_adapter_v1.py` — V2 Program IR/receipt projection into Ω0 objects; no new V2 semantics.
- `tools/tevprober_omega0.py` — exact base/frontier plan sealing and tamper-evident Ω0 campaign contract.
- `RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py` — non-promotional local technical certification with external receipt.
- `schemas/tev-script-omega0-certify-receipt.schema.json` — exact technical receipt schema.
- `tests/test_omega_kernel_v1.py` — K/P/C/R/E model and tamper tests.
- `tests/test_omega_v2_adapter_v1.py` — V2 projection and replay-binding tests.
- `tests/test_tevprober_omega0.py` — frontier/plan hash/non-promotion tests.
- `tests/test_omega0_certify.py` — certifier contract/receipt tests.

**Already present:**
- `docs/superpowers/specs/2026-08-15-tev-script-omega-master-design.md`.
- `docs/superpowers/plans/2026-08-15-tev-script-omega0-kernel-contract.md`.

**Must remain byte-identical to base during Ω0:**
- `CANONICAL_INDEX.json`.
- `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`.
- `tev_script/release_metadata_v2.py`.
- `tev_script/source_program_v2.py`.
- `tev_script/program_ir_v4.py`.
- `tev_script/source_effect_program_v2.py`.
- `tev_script/ir_v4_effects.py`.
- `tev_script/ir_v4_effect_commands.py`.
- `tev_script/program_ir_v4_effect_commands.py`.
- `tev_script/effect_commit_ledger_v2.py`.

---

### Task 1: Add the Ω0 canonical kernel identities and proof envelope

**Files:**
- Create: `tests/test_omega_kernel_v1.py`
- Create: `tev_script/omega_kernel_v1.py`

**Interfaces:**
- Produces `KernelComputationIdentityV1`.
- Produces `ProofEnvelopeV1`.
- Produces `kernel_computation_identity(...) -> KernelComputationIdentityV1`.
- Produces `proof_envelope(...) -> ProofEnvelopeV1`.
- Produces `omega_wire(value) -> dict[str, object]`.
- Produces `omega_hash(value) -> str` using existing `tev_script.canonical.canonical_hash`.

- [ ] **Step 1: Write failing identity tests**

```python
from __future__ import annotations

import dataclasses
import unittest

from tev_script.omega_kernel_v1 import (
    KernelComputationIdentityV1,
    ProofEnvelopeV1,
    kernel_computation_identity,
    omega_hash,
    omega_wire,
    proof_envelope,
)


class OmegaKernelIdentityTests(unittest.TestCase):
    def test_kernel_identity_is_canonical_and_self_hashed(self) -> None:
        identity = kernel_computation_identity(
            language_id="TEV-Script",
            language_version="2.0.0",
            semantic_profile="program-ir-v4-pure",
            program_hash="1" * 64,
            source_semantic_hash="2" * 64,
        )
        self.assertIsInstance(identity, KernelComputationIdentityV1)
        wire = omega_wire(identity)
        declared = wire.pop("identity_hash")
        self.assertEqual(declared, omega_hash(wire))
        self.assertEqual(identity.program_hash, "1" * 64)

    def test_proof_envelope_is_evidence_not_authority(self) -> None:
        envelope = proof_envelope(
            claim_kind="translation_validation",
            subject_hash="1" * 64,
            proof_system="external:test",
            proof_artifact_hash="2" * 64,
        )
        self.assertIsInstance(envelope, ProofEnvelopeV1)
        self.assertFalse(envelope.admission_authority)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_omega_kernel_v1
```

Expected: import failure because `tev_script.omega_kernel_v1` does not exist.

- [ ] **Step 3: Implement minimal canonical models**

Use frozen/slots dataclasses with these exact fields:

```python
@dataclass(frozen=True, slots=True)
class KernelComputationIdentityV1:
    schema: str
    language_id: str
    language_version: str
    semantic_profile: str
    program_hash: str
    source_semantic_hash: str
    identity_hash: str

@dataclass(frozen=True, slots=True)
class ProofEnvelopeV1:
    schema: str
    claim_kind: str
    subject_hash: str
    proof_system: str
    proof_artifact_hash: str
    admission_authority: bool
    envelope_hash: str
```

Exact schemas:

```text
TEV_SCRIPT_OMEGA_KERNEL_COMPUTATION_IDENTITY_V1
TEV_SCRIPT_OMEGA_PROOF_ENVELOPE_V1
```

Validation rules:

- all hashes are lowercase 64-hex;
- identifiers/text are non-empty strings;
- `admission_authority` is always `False` for `proof_envelope()`;
- the final hash is computed from every field except the final hash field;
- `omega_wire()` recursively converts dataclasses/tuples to canonical JSON-compatible values and rejects unsupported objects.

`omega_hash()` delegates to `tev_script.canonical.canonical_hash` and returns bare lowercase hex, matching existing TEV canonical hash style.

- [ ] **Step 4: Run GREEN**

```powershell
python -m unittest -v tests.test_omega_kernel_v1
```

Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_omega_kernel_v1.py tev_script/omega_kernel_v1.py
git commit -m "feat: add Omega kernel identities"
```

---

### Task 2: Add effect sets, explicit resource vectors, and authority grants

**Files:**
- Modify: `tests/test_omega_kernel_v1.py`
- Modify: `tev_script/omega_kernel_v1.py`

**Interfaces:**
- Produces `ResourceBoundV1`.
- Produces `ResourceVectorV1`.
- Produces `EffectSetV1`.
- Produces `AuthorityGrantV1`.
- Produces `AuthorityUseV1`.
- Produces `resource_unknown()`, `resource_upper(value)`, `resource_exact(value)`.
- Produces `compose_resource_sequence(left, right)`.
- Produces `effect_set(effects)`.
- Produces `authority_grant(...)` and `authority_use(...)`.

- [ ] **Step 1: Write failing algebra tests**

```python
from tev_script.omega_kernel_v1 import (
    authority_grant,
    authority_use,
    compose_resource_sequence,
    effect_set,
    resource_exact,
    resource_unknown,
    resource_upper,
    resource_vector,
)

class OmegaAuthorityResourceTests(unittest.TestCase):
    def test_unknown_resource_never_collapses_to_zero(self) -> None:
        left = resource_vector(cpu=resource_upper(10), memory=resource_unknown())
        right = resource_vector(cpu=resource_exact(5), memory=resource_upper(1024))
        combined = compose_resource_sequence(left, right)
        self.assertEqual(combined.cpu.kind, "upper")
        self.assertEqual(combined.cpu.value, 15)
        self.assertEqual(combined.memory.kind, "unknown")
        self.assertIsNone(combined.memory.value)

    def test_effect_set_is_sorted_unique_and_hashed(self) -> None:
        effects = effect_set(("command:file.replace", "observe:file.read", "observe:file.read"))
        self.assertEqual(effects.effects, ("command:file.replace", "observe:file.read"))

    def test_linear_authority_use_consumes_exact_grant(self) -> None:
        grant = authority_grant(
            principal_hash="1" * 64,
            capability_id="file.replace",
            scope_hash="2" * 64,
            duplication_policy="linear",
            resources=resource_vector(effects=resource_upper(1)),
        )
        use = authority_use(
            grant=grant,
            operation="commit",
            subject_hash="3" * 64,
            resources=resource_vector(effects=resource_exact(1)),
            consume=True,
        )
        self.assertEqual(use.grant_hash, grant.grant_hash)
        self.assertTrue(use.consumes_grant)
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_omega_kernel_v1.OmegaAuthorityResourceTests
```

Expected: missing symbols.

- [ ] **Step 3: Implement exact resource representation**

```python
@dataclass(frozen=True, slots=True)
class ResourceBoundV1:
    kind: str                 # exact | upper | provider | unknown
    value: int | None
    authority_hash: str | None

@dataclass(frozen=True, slots=True)
class ResourceVectorV1:
    cpu: ResourceBoundV1
    memory: ResourceBoundV1
    stack: ResourceBoundV1
    io: ResourceBoundV1
    network: ResourceBoundV1
    gpu: ResourceBoundV1
    tasks: ResourceBoundV1
    storage: ResourceBoundV1
    effects: ResourceBoundV1
    communication: ResourceBoundV1
    vector_hash: str
```

Rules:

- exact/upper require integer `value >= 0` and no authority hash;
- provider requires `value >= 0` plus 64-hex `authority_hash`;
- unknown requires `value=None` and `authority_hash=None`;
- sequence composition: if either side unknown, result unknown; otherwise add values and return `exact` only if both exact, otherwise `upper`; provider bounds compose to `upper` after their values are admitted—provider identities remain evidence outside the arithmetic result.

Exact effect model:

```python
@dataclass(frozen=True, slots=True)
class EffectSetV1:
    schema: str
    effects: tuple[str, ...]
    effect_set_hash: str
```

Effect strings must match `^(observe|command|state|compute):[A-Za-z_][A-Za-z0-9_.-]*$`, be unique and lexically sorted.

Exact authority model:

```python
@dataclass(frozen=True, slots=True)
class AuthorityGrantV1:
    schema: str
    principal_hash: str
    capability_id: str
    scope_hash: str
    duplication_policy: str  # reusable | affine | linear
    resources: ResourceVectorV1
    parent_grant_hash: str | None
    grant_hash: str

@dataclass(frozen=True, slots=True)
class AuthorityUseV1:
    schema: str
    grant_hash: str
    operation: str
    subject_hash: str
    resources: ResourceVectorV1
    consumes_grant: bool
    use_hash: str
```

Ω0 validates structure and identity. Stateful no-double-consume/revoke semantics are intentionally Ω1, not hidden inside Ω0.

- [ ] **Step 4: Run GREEN**

```powershell
python -m unittest -v tests.test_omega_kernel_v1
```

Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_omega_kernel_v1.py tev_script/omega_kernel_v1.py
git commit -m "feat: add Omega authority and resource models"
```

---

### Task 3: Add observation evidence, epoch identity, and continuation receipts

**Files:**
- Modify: `tests/test_omega_kernel_v1.py`
- Modify: `tev_script/omega_kernel_v1.py`

**Interfaces:**
- Produces `ObservationEvidenceV1`.
- Produces `EpochIdentityV1`.
- Produces `ContinuationReceiptV1`.
- Produces `observation_evidence(...)`.
- Produces `epoch_identity(...)`.
- Produces `continuation_receipt(...)`.
- Produces `verify_continuation_link(previous, current) -> bool`.

- [ ] **Step 1: Write failing continuation tests**

```python
from tev_script.omega_kernel_v1 import (
    continuation_receipt,
    epoch_identity,
    observation_evidence,
    verify_continuation_link,
)

class OmegaEpochTests(unittest.TestCase):
    def test_observation_turns_nondeterminism_into_explicit_evidence(self) -> None:
        evidence = observation_evidence(
            capability_id="clock.now",
            contract_hash="1" * 64,
            request_hash="2" * 64,
            result_hash="3" * 64,
            transcript_hash="4" * 64,
        )
        self.assertEqual(evidence.capability_id, "clock.now")

    def test_epoch_chain_consumes_exact_previous_continuation(self) -> None:
        first_epoch = epoch_identity(
            epoch_index=0,
            computation_hash="1" * 64,
            input_state_hash="2" * 64,
            authority_hash="3" * 64,
            previous_continuation_hash=None,
        )
        first = continuation_receipt(
            epoch=first_epoch,
            result_hash="4" * 64,
            state_hash="5" * 64,
            observations_hash="6" * 64,
            effects_hash="7" * 64,
            resources_hash="8" * 64,
        )
        second_epoch = epoch_identity(
            epoch_index=1,
            computation_hash="9" * 64,
            input_state_hash="5" * 64,
            authority_hash="a" * 64,
            previous_continuation_hash=first.continuation_hash,
        )
        second = continuation_receipt(
            epoch=second_epoch,
            result_hash="b" * 64,
            state_hash="c" * 64,
            observations_hash="d" * 64,
            effects_hash="e" * 64,
            resources_hash="f" * 64,
        )
        self.assertTrue(verify_continuation_link(first, second))
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_omega_kernel_v1.OmegaEpochTests
```

Expected: missing symbols.

- [ ] **Step 3: Implement exact epoch/evidence structures**

```python
@dataclass(frozen=True, slots=True)
class ObservationEvidenceV1:
    schema: str
    capability_id: str
    contract_hash: str
    request_hash: str
    result_hash: str
    transcript_hash: str
    evidence_hash: str

@dataclass(frozen=True, slots=True)
class EpochIdentityV1:
    schema: str
    epoch_index: int
    computation_hash: str
    input_state_hash: str
    authority_hash: str
    previous_continuation_hash: str | None
    epoch_hash: str

@dataclass(frozen=True, slots=True)
class ContinuationReceiptV1:
    schema: str
    epoch_hash: str
    epoch_index: int
    previous_continuation_hash: str | None
    result_hash: str
    state_hash: str
    observations_hash: str
    effects_hash: str
    resources_hash: str
    continuation_hash: str
```

Rules:

- epoch index is integer `>= 0`;
- epoch 0 requires `previous_continuation_hash=None`;
- epoch >0 requires a 64-hex previous continuation;
- `verify_continuation_link(previous,current)` returns true only when `current.epoch_index == previous.epoch_index + 1` and `current.previous_continuation_hash == previous.continuation_hash`;
- state/result/effect/resource hashes are explicit even if they represent an empty canonical object; no field is omitted to mean zero/none.

- [ ] **Step 4: Add tamper negatives**

Copy one continuation with a changed `state_hash` while preserving the old `continuation_hash`; `validate_continuation_receipt()` must raise `TevScriptError` with code beginning `TEVS_OMEGA_`.

- [ ] **Step 5: Run GREEN**

```powershell
python -m unittest -v tests.test_omega_kernel_v1
```

Expected: PASS, zero skips.

- [ ] **Step 6: Commit**

```powershell
git add tests/test_omega_kernel_v1.py tev_script/omega_kernel_v1.py
git commit -m "feat: add Omega epoch continuation model"
```

---

### Task 4: Project validated V2 Program IR and receipts into Ω0

**Files:**
- Create: `tests/test_omega_v2_adapter_v1.py`
- Create: `tev_script/omega_v2_adapter_v1.py`

**Interfaces:**
- Consumes existing `validate_program_ir_v4`, `run_program_ir_v4`, and canonical V2 receipt fields.
- Produces `project_program_ir_v4(raw: Mapping[str, Any]) -> KernelComputationIdentityV1`.
- Produces `project_run_receipt_v4(raw_ir, receipt) -> dict[str, object]` containing computation/result/state/transcript/effect hashes without inventing semantics absent from the V2 receipt.
- Produces `omega_epoch_from_v2(...) -> tuple[EpochIdentityV1, ContinuationReceiptV1]`.

- [ ] **Step 1: Write failing pure/recursive/effects projection tests**

Use three existing valid fixtures built through public V2 APIs:

```python
import unittest

from tev_script.omega_v2_adapter_v1 import project_program_ir_v4
from tev_script.program_ir_v4 import (
    export_program_ir_v4_pure,
    export_program_ir_v4_recursive,
)
from tev_script.source_program_v2 import compile_program_v2


class OmegaV2AdapterTests(unittest.TestCase):
    def test_pure_ir_projection_binds_existing_v2_hashes(self) -> None:
        source = 'script Demo version "2.0.0"; fn f(x:Int)->Int=x+1; entry main:Int=f(4);'
        ir = export_program_ir_v4_pure(compile_program_v2(source))
        identity = project_program_ir_v4(ir)
        self.assertEqual(identity.program_hash, ir["program_ir_hash"])
        self.assertEqual(identity.source_semantic_hash, ir["source"]["semantic_hash"])
        self.assertEqual(identity.semantic_profile, "program-ir-v4-pure")
```

Add equivalent recursive and Effects R1/R2 fixture tests using existing builder APIs from `tests/test_program_ir_v4_recursive.py`, `tests/test_program_ir_v4_effects.py`, and `tests/test_program_ir_v4_effect_commands.py`. Copy the fixture construction into this test; do not import another test module.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_omega_v2_adapter_v1
```

Expected: import failure because adapter does not exist.

- [ ] **Step 3: Implement projection after validation only**

`project_program_ir_v4(raw)` must:

1. call existing `validate_program_ir_v4(raw)` first;
2. read the already-validated `program_ir_hash` and source semantic hash;
3. map exact V2 schemas/profiles to one of:
   - `program-ir-v4-pure`,
   - `program-ir-v4-recursive`,
   - `program-ir-v4-effects-r1`,
   - `program-ir-v4-effects-r2`;
4. return `kernel_computation_identity(language_id="TEV-Script", language_version="2.0.0", ...)`;
5. reject unknown V2 schema/profile rather than guessing.

Do not reimplement V2 validation in the adapter.

- [ ] **Step 4: Implement V2 result projection without inventing unavailable data**

For a V2 run receipt, construct a canonical projection map with exact keys:

```text
schema
computation_identity_hash
program_ir_hash
result_hash
state_hash
observation_transcript_hash
effect_receipt_hash
projection_hash
```

If a V2 profile does not have state/observation/effect data, use `omega_hash({"schema":"TEV_SCRIPT_OMEGA_ABSENT_V1","kind":"state"})` (and corresponding kind) rather than empty string or zero hash. This makes absence explicit and deterministic.

- [ ] **Step 5: Implement `omega_epoch_from_v2`**

Arguments:

```python
def omega_epoch_from_v2(
    raw_ir: Mapping[str, Any],
    receipt: Any,
    *,
    epoch_index: int,
    input_state_hash: str,
    authority_hash: str,
    previous_continuation_hash: str | None,
    resources: ResourceVectorV1,
) -> tuple[EpochIdentityV1, ContinuationReceiptV1]:
```

It projects/validates IR, constructs the result projection, creates epoch identity, hashes the resource vector, then creates the continuation receipt.

- [ ] **Step 6: Run GREEN**

```powershell
python -m unittest -v tests.test_omega_v2_adapter_v1
```

Expected: PASS, zero skips.

- [ ] **Step 7: Commit**

```powershell
git add tests/test_omega_v2_adapter_v1.py tev_script/omega_v2_adapter_v1.py
git commit -m "feat: project V2 artifacts into Omega kernel"
```

---

### Task 5: Add a TEVProber-style exact Ω0 frontier gate

**Files:**
- Create: `tests/test_tevprober_omega0.py`
- Create: `tools/tevprober_omega0.py`

**Interfaces:**
- Produces exact `BASE_SHA`, `BASE_TREE`, `OMEGA0_FRONTIER`.
- Produces `plan(changed_paths)`, `verify_plan(plan)`, and `resolve_changed_paths()`.
- Has `promotion_authority_bool=False` and `language_stable_claim_bool=False` permanently.

- [ ] **Step 1: Write failing probe tests**

Exact frontier:

```python
OMEGA0_FRONTIER = (
    "RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py",
    "docs/superpowers/plans/2026-08-15-tev-script-omega0-kernel-contract.md",
    "docs/superpowers/specs/2026-08-15-tev-script-omega-master-design.md",
    "schemas/tev-script-omega0-certify-receipt.schema.json",
    "tests/test_omega0_certify.py",
    "tests/test_omega_kernel_v1.py",
    "tests/test_omega_v2_adapter_v1.py",
    "tests/test_tevprober_omega0.py",
    "tev_script/omega_kernel_v1.py",
    "tev_script/omega_v2_adapter_v1.py",
    "tools/tevprober_omega0.py",
)
```

Tests require exact frontier => READY; adding `tev_script/program_ir_v4.py`, `source_program_v2.py`, release metadata, or V2 feature matrix => HOLD; plan tampering => reject.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_tevprober_omega0
```

Expected: import failure.

- [ ] **Step 3: Implement probe using the existing TEVProber pattern**

Use deterministic canonical JSON, SHA-256 plan seal, `git diff BASE_SHA...HEAD`, and `git status --porcelain=v1`. Do not depend on TEVProver-CUOFC. Environment output is bounded. The plan is measurement/campaign authority only.

- [ ] **Step 4: Run GREEN**

```powershell
python -m unittest -v tests.test_tevprober_omega0
```

Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tests/test_tevprober_omega0.py tools/tevprober_omega0.py
git commit -m "test: seal Omega0 causal frontier"
```

---

### Task 6: Add Ω0 technical certification and V2 non-regression gate

**Files:**
- Create: `schemas/tev-script-omega0-certify-receipt.schema.json`
- Create: `tests/test_omega0_certify.py`
- Create: `RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py`

**Interfaces:**
- CLI: `python RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py --expected-base <sha> --receipt-out <external-path>`.
- Receipt schema: `TEV_SCRIPT_OMEGA0_CERTIFY_RECEIPT_V1`.
- Always emits `LANGUAGE_STABLE=NO`.

- [ ] **Step 1: Write failing certifier tests**

Tests require:

- exact clean `agent/` branch identity;
- expected base is exact stable V2 base and ancestor;
- `origin/main` remains exact V2 stable base for this Ω0 campaign;
- receipt path external and create-once;
- exact Ω0 frontier plan READY;
- Ω test suite PASS;
- fresh `RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --profile stable --expected-base <stable-base>` is not used on Ω branch because Ω changes are not V2 stable release diff; instead run full existing `unittest discover` as non-regression plus direct V2 authority validation against the unchanged base files;
- no V2 governed file changed from base;
- receipt self-hash validates;
- `promotion_authority=false`, `language_stable=false`.

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_omega0_certify
```

Expected: missing certifier/schema.

- [ ] **Step 3: Implement exact receipt body**

Receipt fields:

```text
schema
repository
branch
commit_sha
tree_sha
base_sha
base_tree_sha
omega_master_design_sha256
omega_plan_sha256
omega_frontier_plan_hash
omega_test_count
omega_skipped_tests
full_test_count
full_skipped_tests
v2_governed_files_unchanged
v2_authority_validation
promotion_authority
language_stable
certify_full
receipt_hash
```

Required claims:

```text
promotion_authority = false
language_stable = false
certify_full = true
```

The certifier must reject any change to V2 semantic/release authority files listed under Global Constraints.

- [ ] **Step 4: Run focal GREEN**

```powershell
python -m unittest -v tests.test_omega_kernel_v1 tests.test_omega_v2_adapter_v1 tests.test_tevprober_omega0 tests.test_omega0_certify
```

Expected: PASS, zero skips.

- [ ] **Step 5: Run full regression**

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

Expected: PASS, zero skips. Record exact count.

- [ ] **Step 6: Run Ω0 certifier with external receipt**

```powershell
python .\RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py `
  --expected-base 2bdb047dcad41f9d112219bd65925c25668c02e0 `
  --receipt-out C:\TEV\WORK\TEV-SCRIPT-OMEGA0\omega0-certify.json
```

Expected terminal witnesses:

```text
OMEGA0_FRONTIER=PASS
OMEGA0_KERNEL=PASS
OMEGA0_V2_ADAPTER=PASS
V2_NON_REGRESSION=PASS
CERTIFY_OMEGA0=PASS
LANGUAGE_STABLE=NO
```

- [ ] **Step 7: Commit**

```powershell
git add schemas/tev-script-omega0-certify-receipt.schema.json tests/test_omega0_certify.py RUN_TEV_SCRIPT_OMEGA0_CERTIFY.py
git commit -m "feat: certify Omega0 kernel contract"
```

---

## Final Ω0 review gate

After Task 6:

```powershell
git diff --name-only 2bdb047dcad41f9d112219bd65925c25668c02e0...HEAD
```

Must equal exactly `OMEGA0_FRONTIER`.

Then verify:

```text
V2_MAIN_UNCHANGED=PASS
V2_GOVERNED_FILES_UNCHANGED=PASS
V2_EXISTING_REGRESSION=PASS
KERNEL_IDENTITY=PASS
PROOF_ENVELOPE=PASS
AUTHORITY_GRANT_MODEL=PASS
RESOURCE_VECTOR_MODEL=PASS
EFFECT_SET_MODEL=PASS
OBSERVATION_EVIDENCE=PASS
CONTINUATION_RECEIPT=PASS
TAMPER_NEGATIVES=PASS
DETERMINISTIC_REPLAY_BINDING=PASS
PROMOTION_AUTHORITY=FALSE
LANGUAGE_STABLE=NO
```

Only after this gate passes should Ω1 (stateful authority algebra) and Ω2 (durable epoch/checkpoint runtime) begin.
