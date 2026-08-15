# TEV Script V2.0.x Hardening + Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, hash-sealed hardening and performance harness for stable TEV Script V2.0.0, record a trustworthy baseline, and decide from measured evidence whether any implementation optimization is justified without changing V2 semantics.

**Architecture:** Add repository-owned tooling outside the V2 semantic-authority surface. `tools/v2_hardening_corpus.py` owns deterministic benchmark/adversarial case construction and execution adapters. `tools/tevprober_v2_hardening_performance.py` owns Git identity, causal-frontier sealing, measurement, comparison, external receipts, and CLI orchestration. New tests import only these `tools/` modules so the stable V2 feature matrix does not need to change merely to enumerate campaign tests.

**Tech Stack:** Python 3.11+ standard library only for campaign code (`dataclasses`, `hashlib`, `hmac`, `json`, `statistics`, `subprocess`, `tempfile`, `time`, `tracemalloc`); existing TEV Script V2 Python implementation; `unittest`; canonical SHA-256; external JSON receipts. No new runtime dependency and no GitHub Actions.

## Global Constraints

- Stable semantic base is exactly `2bdb047dcad41f9d112219bd65925c25668c02e0` with tree `aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8`.
- Stable Admission receipt authority remains `4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6`; this campaign never rewrites or reinterprets it.
- Language version remains exactly `2.0.0`.
- Do not modify grammar, parser acceptance/rejection semantics, static semantics, Program IR V4 schema/meaning, portable value model, capability ABI, canonical hashing, conformance receipt meaning, or stable-admission authority.
- Do not modify `CANONICAL_INDEX.json`, `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`, V2 schemas, or `tev_script/release_metadata_v2.py` in this infrastructure plan.
- New tests must not directly import V2 governed implementation modules; they import `tools.v2_hardening_corpus` or `tools.tevprober_v2_hardening_performance`. This keeps `tools/validate_v2_authority.py::_require_test_inventory_closure` satisfied without changing the stable feature matrix.
- No security check may be removed or bypassed for performance.
- Missing capability, exhausted budget, malformed IR, hash mismatch, unsupported secure primitive, and authority mismatch continue to fail closed.
- Benchmark comparisons require the same corpus hash and compatible environment fingerprint.
- Final timing uses no profiler; `cProfile` may be used only after a phase-level hotspot is established and only as diagnostic evidence.
- Baseline and candidate receipts are written outside the repository and source execution leaves the repository clean.
- Branch is `agent/tev-script-v2-hardening-performance-v1`; no merge, tag, release, stable promotion, or `main` mutation without explicit authorization.
- This plan stops after infrastructure + baseline + hotspot classification. Any actual optimization receives a separate TDD plan after a measured hotspot exists.

---

## File map

**Create:**
- `tools/v2_hardening_corpus.py` — deterministic benchmark/adversarial case definitions, corpus hashing, semantic witnesses, adversarial execution, and per-case measurements.
- `tools/tevprober_v2_hardening_performance.py` — exact Git/frontier policy, sealed plans, aggregation, hardening runner, comparison gate, external receipts, CLI.
- `tests/test_tevprober_v2_hardening_performance.py` — probe/frontier/sealing/measurement/comparison/CLI regression tests; imports only `tools.*`.
- `tests/test_v2_hardening_adversarial.py` — deterministic finite adversarial campaign tests through `tools.v2_hardening_corpus`; imports no governed `tev_script.*` module directly.

**Already changed on this campaign branch:**
- `docs/superpowers/specs/2026-08-15-tev-script-v2-hardening-performance-design.md`
- `docs/superpowers/plans/2026-08-15-tev-script-v2-hardening-performance.md`

**Must remain unchanged:**
- `CANONICAL_INDEX.json`
- `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- `schemas/tev-script-v2-descriptor.schema.json`
- `schemas/tev-script-program-ir-v4.schema.json`
- `schemas/tev-script-v2-filesystem-artifacts.schema.json`
- `schemas/tev-script-v2-certify-full-receipt.schema.json`
- `tev_script/release_metadata_v2.py`
- every existing parser/compiler/runtime implementation file under `tev_script/`

---

### Task 1: Add the hash-sealed probe contract and exact infrastructure frontier

**Files:**
- Create: `tools/tevprober_v2_hardening_performance.py`
- Create: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces `BASE_SHA: str`, `BASE_TREE: str`, `PLAN_SCHEMA: str`, `RUN_SCHEMA: str`.
- Produces `normalize_paths(values: Sequence[str]) -> tuple[str, ...]`.
- Produces `plan(changed_paths: Sequence[str]) -> dict[str, Any]`.
- Produces `verify_plan(value: Mapping[str, Any]) -> bool`.
- Produces `resolve_changed_paths() -> tuple[str, ...]`.
- Produces `environment_fingerprint() -> dict[str, Any]`.

- [ ] **Step 1: Write the failing contract tests**

```python
from __future__ import annotations

import copy
import unittest

from tools import tevprober_v2_hardening_performance as probe

EXPECTED_FRONTIER = (
    "docs/superpowers/plans/2026-08-15-tev-script-v2-hardening-performance.md",
    "docs/superpowers/specs/2026-08-15-tev-script-v2-hardening-performance-design.md",
    "tests/test_tevprober_v2_hardening_performance.py",
    "tests/test_v2_hardening_adversarial.py",
    "tools/tevprober_v2_hardening_performance.py",
    "tools/v2_hardening_corpus.py",
)

class V2HardeningProbeContractTests(unittest.TestCase):
    def test_exact_frontier_is_ready_and_non_promotional(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        self.assertEqual(value["status"], "READY")
        self.assertEqual(tuple(value["changed_paths"]), EXPECTED_FRONTIER)
        self.assertEqual(value["base_sha"], "2bdb047dcad41f9d112219bd65925c25668c02e0")
        self.assertEqual(value["base_tree"], "aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8")
        self.assertIs(value["promotion_authority_bool"], False)
        self.assertTrue(probe.verify_plan(value))

    def test_semantic_implementation_path_holds(self) -> None:
        value = probe.plan((*EXPECTED_FRONTIER, "tev_script/program_ir_v4.py"))
        self.assertEqual(value["status"], "HOLD")
        self.assertFalse(value["promotion_authority_bool"])

    def test_plan_tamper_is_rejected(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        tampered = copy.deepcopy(value)
        tampered["metric_policy"]["trials"] = 1
        self.assertFalse(probe.verify_plan(tampered))
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: import failure because `tools/tevprober_v2_hardening_performance.py` does not exist.

- [ ] **Step 3: Implement the exact plan contract**

Use these exact constants and policies:

```python
ROOT = Path(__file__).resolve().parents[1]
BASE_SHA = "2bdb047dcad41f9d112219bd65925c25668c02e0"
BASE_TREE = "aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8"
PLAN_SCHEMA = "tev-script-v2-hardening-performance-plan/v1"
RUN_SCHEMA = "tev-script-v2-hardening-performance-run/v1"
INFRASTRUCTURE_FRONTIER = (
    "docs/superpowers/plans/2026-08-15-tev-script-v2-hardening-performance.md",
    "docs/superpowers/specs/2026-08-15-tev-script-v2-hardening-performance-design.md",
    "tests/test_tevprober_v2_hardening_performance.py",
    "tests/test_v2_hardening_adversarial.py",
    "tools/tevprober_v2_hardening_performance.py",
    "tools/v2_hardening_corpus.py",
)
METRIC_POLICY = {
    "warmups": 2,
    "trials": 7,
    "primary_aggregate": "median",
    "max_relative_dispersion": 0.20,
    "material_improvement_ratio": 0.10,
    "max_unexplained_regression_ratio": 0.05,
}
```

Canonical hashing is exactly:

```python
def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def sha256_obj(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_bytes(value)).hexdigest()
```

`normalize_paths` rejects strings-as-sequences, empty paths, absolute paths, parent traversal, NUL, and newline; it returns unique sorted slash-normalized paths. `plan` returns READY only when the changed path set is exactly `INFRASTRUCTURE_FRONTIER`; otherwise HOLD with `out_of_frontier:` and `missing_frontier:` reasons. `verify_plan` rebuilds the plan from `changed_paths` and compares both `plan_hash` and canonical bytes using `hmac.compare_digest` for the hash.

`resolve_changed_paths` reads committed changes from `git diff --name-only BASE_SHA...HEAD --` plus tracked/untracked pending paths from `git status --porcelain=v1 --untracked-files=all`. `environment_fingerprint` records only `sys.version_info[:3]`, `sys.implementation.name`, `platform.system()`, `platform.release()`, `platform.machine()`, and `os.cpu_count()` and includes a canonical fingerprint hash.

- [ ] **Step 4: Run GREEN**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "test: seal V2 hardening probe contract"
```

---

### Task 2: Add the deterministic 14-family benchmark corpus and semantic witnesses

**Files:**
- Create: `tools/v2_hardening_corpus.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces `BenchmarkCaseV2(case_id: str, family: str, scale: int, kind: str, payload: dict[str, Any])`.
- Produces `build_benchmark_corpus() -> tuple[BenchmarkCaseV2, ...]` with exactly 42 cases.
- Produces `benchmark_corpus_hash() -> str`.
- Produces `semantic_witness(case: BenchmarkCaseV2) -> dict[str, Any]`.

- [ ] **Step 1: Write corpus closure and repeatability tests**

```python
from tools import v2_hardening_corpus as corpus

class V2BenchmarkCorpusTests(unittest.TestCase):
    def test_corpus_is_exactly_fourteen_families_times_three_scales(self) -> None:
        cases = corpus.build_benchmark_corpus()
        self.assertEqual(len(cases), 42)
        self.assertEqual(len({case.case_id for case in cases}), 42)
        self.assertEqual({case.scale for case in cases}, {1, 2, 3})
        self.assertEqual(
            {case.family for case in cases},
            {
                "tiny_pure", "collection_heavy", "generic_specialization",
                "protocol_associated_type", "bounded_recursion", "wide_task_dag",
                "deep_task_dag", "observation_heavy", "effect_plan_heavy",
                "local_module_bundle", "signed_remote_module_bundle", "filesystem_read",
                "filesystem_replace", "canonical_receipt_heavy",
            },
        )

    def test_tiny_pure_semantic_witness_replays_exactly(self) -> None:
        case = next(item for item in corpus.build_benchmark_corpus() if item.case_id == "tiny_pure.s1")
        self.assertEqual(corpus.semantic_witness(case), corpus.semantic_witness(case))
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: import failure for `tools.v2_hardening_corpus`.

- [ ] **Step 3: Implement the case model and exact inventory formulas**

Use this exact family table. Each row generates scales 1, 2, 3 and `case_id=f"{family}.s{scale}"`.

| family | kind | deterministic payload formula |
|---|---|---|
| `tiny_pure` | `source_pure` | source `script P{scale} version "2.0.0"; fn add(x:Int)->Int=x+{scale}; entry main:Int=add(41);` |
| `collection_heavy` | `source_pure` | `length=(3,8,16)[scale-1]`; source contains `generic fn middle<T>(xs:Array<T,length>)->T=array.get(xs,length//2);` and an integer array literal `0..length-1` |
| `generic_specialization` | `registry_generic` | `specializations=(2,4,7)[scale-1]`; instantiate one registered identity template over the ordered prefix of `("Int","Text","Bool","Rat","Vec2","Vec3","Unit")` |
| `protocol_associated_type` | `source_pure` | use one fixed valid protocol/associated-type source from `tests/test_source_associated_types_v2.py`; repeat independent concrete impl blocks `(1,2,4)[scale-1]` with unique names |
| `bounded_recursion` | `source_recursive` | factorial source with `n=(4,6,8)[scale-1]` and `max_depth=(8,10,12)[scale-1]` |
| `wide_task_dag` | `task_scheduler` | `width=(4,16,64)[scale-1]`, `workers=4`, tasks are canonical maps `{"index": i}` and child result is deterministic `i*i` |
| `deep_task_dag` | `source_pure` | build a nested pure task expression with depth `(2,4,6)[scale-1]` using the same source form exercised by `tests/test_task_dag_v2.py` |
| `observation_heavy` | `effects_ir` | build one observation capability and `(2,8,32)[scale-1]` deterministic transcript calls |
| `effect_plan_heavy` | `effects_r2_plan` | build `(2,8,32)[scale-1]` authorized file-effect intents against temporary fixture paths, planning only; do not commit physical effects during timing |
| `local_module_bundle` | `local_module` | create `(2,8,24)[scale-1]` modules in a temporary directory; one root imports every leaf in canonical name order |
| `signed_remote_module_bundle` | `signed_remote_module` | create `(1,4,12)[scale-1]` locally signed module payloads using the same Ed25519 fixture strategy as `tests/test_signed_remote_module_manifest_v2.py`; no network |
| `filesystem_read` | `filesystem_read` | temporary regular file sizes `(4 KiB,64 KiB,512 KiB)`; perform handle-scoped read within the 1 MiB limit |
| `filesystem_replace` | `filesystem_replace` | temporary replacement payload sizes `(4 KiB,64 KiB,512 KiB)`; perform same-directory authorized replace in a disposable directory |
| `canonical_receipt_heavy` | `canonical` | canonical object contains `(32,256,2048)[scale-1]` records with integer/string fields and is hashed twice to prove deterministic bytes |

`benchmark_corpus_hash()` is SHA-256 over canonical JSON of `[dataclasses.asdict(case) for case in cases]`. No case payload contains an absolute path, temporary directory name, random value, timestamp, object repr, or process id.

- [ ] **Step 4: Implement the semantic witness dispatch with exact existing APIs**

Use this dispatch map:

```python
_WITNESS_BUILDERS = {
    "source_pure": _witness_source_pure,
    "source_recursive": _witness_source_recursive,
    "registry_generic": _witness_registry_generic,
    "task_scheduler": _witness_task_scheduler,
    "effects_ir": _witness_effects_ir,
    "effects_r2_plan": _witness_effects_r2_plan,
    "local_module": _witness_local_module,
    "signed_remote_module": _witness_signed_remote_module,
    "filesystem_read": _witness_filesystem_read,
    "filesystem_replace": _witness_filesystem_replace,
    "canonical": _witness_canonical,
}
```

For pure source, use exactly `compile_and_run_program_v2`, `compile_program_v2`, `export_program_ir_v4_pure`, `validate_program_ir_v4_pure`, `canonical_program_ir_v4_bytes`, and `run_program_ir_v4_pure`, matching `tests/test_program_ir_v4.py`. Reject source/portable result-hash divergence.

For recursive source, use `compile_and_run_program_v2`, `export_program_ir_v4_recursive`, `validate_program_ir_v4_recursive`, `canonical_program_ir_v4_bytes`, and `run_program_ir_v4_recursive`, matching `tests/test_program_ir_v4_recursive.py`.

For effects, use `build_type_table_v4`, `build_state_schema_v4`, `build_capability_table_v4`, `build_effect_action_v4`, `build_effect_scenario_v4`, `build_program_ir_v4_effects`, `validate_program_ir_v4_effects`, and `run_program_ir_v4_effects`, matching `tests/test_program_ir_v4_effects.py`.

For generic registry pressure, use `GenericRegistryV2` and `GenericPureFunctionRegistryV2`; register one `identity<T>(x:T)->T` template with body `{"op":"PARAM","name":"x","type":"T"}`, instantiate the declared ordered type prefix, and include sorted callable IDs in the witness, matching `tests/test_generic_functions_v2.py`.

For task scheduling, use `BoundedThreadTaskStrategyV2(worker_count=4).run(...)`; witness contains canonical ordered child results, never physical completion order.

For module, signed-module, filesystem, and Effects R2 planning families, call the same public functions already exercised by their respective existing test modules; the witness includes only canonical hashes/counts/result identities and excludes temporary paths. Any fixture cleanup happens in `finally`/temporary-directory context managers.

Every witness must be canonicalizable and include `case_id`, `family`, `scale`, `kind`, and `language_version="2.0.0"`.

- [ ] **Step 5: Run GREEN and repeatability check**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
python -c "from tools.v2_hardening_corpus import benchmark_corpus_hash; a=benchmark_corpus_hash(); b=benchmark_corpus_hash(); print(a); print(b); assert a==b"
```

Expected: PASS and identical hashes.

- [ ] **Step 6: Commit**

```powershell
git add tools/v2_hardening_corpus.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "test: add deterministic V2 benchmark corpus"
```

---

### Task 3: Add the finite adversarial mutation campaign

**Files:**
- Modify: `tools/v2_hardening_corpus.py`
- Create: `tests/test_v2_hardening_adversarial.py`

**Interfaces:**
- Produces `AdversarialCaseV2(case_id: str, family: str, mutation: str, expected_outcome: str, expected_diagnostic_codes: tuple[str, ...])`.
- Produces `build_adversarial_cases() -> tuple[AdversarialCaseV2, ...]` with exactly 48 cases.
- Produces `adversarial_corpus_hash() -> str`.
- Produces `run_adversarial_case(case: AdversarialCaseV2) -> dict[str, Any]`.

- [ ] **Step 1: Write the exact finite-campaign tests**

```python
from __future__ import annotations

import unittest
from tools import v2_hardening_corpus as corpus

class V2AdversarialCampaignTests(unittest.TestCase):
    def test_campaign_has_exactly_forty_eight_cases_and_replays(self) -> None:
        cases = corpus.build_adversarial_cases()
        self.assertEqual(len(cases), 48)
        self.assertEqual(len({case.case_id for case in cases}), 48)
        left = [corpus.run_adversarial_case(case) for case in cases]
        right = [corpus.run_adversarial_case(case) for case in cases]
        self.assertEqual(left, right)
        self.assertTrue(all(item["status"] == "PASS" for item in left))
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_v2_hardening_adversarial
```

Expected: missing adversarial API failures.

- [ ] **Step 3: Define these exact 48 case IDs**

Eight cases per family:

```text
source.malformed_utf8_file
source.truncated_token
source.nesting_limit_plus_one
source.reserved_symbol_collision
source.invalid_protocol_constraint
source.recursion_contract_violation
source.task_bound_plus_one
source.oversize_source

program_ir_v4.root_extra_field
program_ir_v4.wrong_schema
program_ir_v4.outer_hash_tamper
program_ir_v4.body_rehash_attack
program_ir_v4.type_table_rehash_attack
program_ir_v4.static_bound_rehash_attack
program_ir_v4.expected_hash_pin_mismatch
program_ir_v4.expected_source_pin_mismatch

capability_effect.missing_capability
capability_effect.extra_ungranted_capability
capability_effect.transcript_hash_mismatch
capability_effect.argument_type_mismatch
capability_effect.result_type_mismatch
capability_effect.effect_intent_tamper
capability_effect.double_commit
capability_effect.provider_response_mismatch

filesystem.parent_traversal
filesystem.symlink_or_reparse_escape
filesystem.root_identity_substitution
filesystem.oversize_read
filesystem.replace_race
filesystem.unsupported_secure_primitive
filesystem.absolute_path_escape
filesystem.nul_path

remote_module_signature.bad_signature
remote_module_signature.wrong_public_key_pin
remote_module_signature.body_hash_mismatch
remote_module_signature.manifest_hash_mismatch
remote_module_signature.transport_pin_mismatch
remote_module_signature.bundle_parent_escape
remote_module_signature.bundle_absolute_path
remote_module_signature.duplicate_bundle_path

receipt_canonicalization.field_reorder
receipt_canonicalization.field_insert
receipt_canonicalization.field_remove
receipt_canonicalization.hash_substitute
receipt_canonicalization.numeric_string_substitute
receipt_canonicalization.unicode_substitute
receipt_canonicalization.identity_mismatch
receipt_canonicalization.replay_result_mismatch
```

Every case has a predeclared `expected_outcome` of `REJECT` or `ACCEPT_CANONICAL_EQUIVALENT`. A case with `REJECT` passes only when the adapter receives `TevScriptError` with a code from the case's explicit code tuple, or the exact documented validation exception for signed-envelope verification. `field_reorder` is `ACCEPT_CANONICAL_EQUIVALENT` and passes only when canonical bytes/hash remain identical. Unexpected exception classes, hangs, subprocess non-termination, or silent acceptance of a REJECT case fail the campaign.

Use temporary local fixtures only. `malformed_utf8_file` writes invalid bytes and exercises the CLI/file-ingestion boundary; it must not convert invalid bytes to a Python string first. `oversize_source` uses `MAX_SOURCE_BYTES_V2 + 1` ASCII bytes. `oversize_read` uses `MAX_FILE_READ_BYTES_V2 + 1` bytes. IR rehash attacks recompute only the outer hash after mutating inner bound/hash-protected content, matching the existing Program IR V4 negative tests.

- [ ] **Step 4: Run GREEN twice**

```powershell
python -m unittest -v tests.test_v2_hardening_adversarial
python -m unittest -v tests.test_v2_hardening_adversarial
```

Expected: both runs PASS, exactly 48 cases, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tools/v2_hardening_corpus.py tests/test_v2_hardening_adversarial.py
git commit -m "test: add finite V2 adversarial campaign"
```

---

### Task 4: Add phase-level measurement and sealed external baseline receipts

**Files:**
- Modify: `tools/v2_hardening_corpus.py`
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces `measure_once(case: BenchmarkCaseV2) -> dict[str, int | None]`.
- Produces `aggregate_samples(values: Sequence[int]) -> dict[str, int | float]`.
- Produces `measure_case(case: BenchmarkCaseV2, *, warmups: int = 2, trials: int = 7) -> dict[str, Any]`.
- Produces `run_baseline(probe_plan: Mapping[str, Any]) -> dict[str, Any]`.
- Produces `verify_run_receipt(value: Mapping[str, Any]) -> bool`.
- Produces `write_external_receipt_once(path: Path, receipt: Mapping[str, Any]) -> Path`.

- [ ] **Step 1: Write aggregation and receipt-tamper tests**

```python
def test_metric_aggregate_uses_median(self) -> None:
    value = probe.aggregate_samples([100, 101, 99, 100, 100, 102, 98])
    self.assertEqual(value["median"], 100)
    self.assertEqual(value["minimum"], 98)
    self.assertEqual(value["maximum"], 102)
    self.assertLess(value["relative_dispersion"], 0.05)

def test_run_receipt_tamper_is_rejected(self) -> None:
    receipt = probe.seal_run({"schema": probe.RUN_SCHEMA, "status": "PASS"})
    self.assertTrue(probe.verify_run_receipt(receipt))
    tampered = dict(receipt)
    tampered["status"] = "FAIL"
    self.assertFalse(probe.verify_run_receipt(tampered))
```

- [ ] **Step 2: Run RED**

Run the focal probe test module. Expected: missing measurement/run APIs.

- [ ] **Step 3: Implement explicit timing boundaries**

For `source_pure`, measure these exact boundaries independently using `time.perf_counter_ns()`:

```text
parse_ns                     parse_program_v2(source)
compile_ns                   compile_parsed_program_v2(parsed)
ir_export_ns                 export_program_ir_v4_pure(compiled)
ir_validation_ns             validate_program_ir_v4_pure(ir)
canonicalization_ns          canonical_program_ir_v4_bytes(ir)
execution_receipt_ns         run_program_ir_v4_pure(ir)
```

For `source_recursive`, use the recursive export/validate/run functions. For non-source cases expose named boundaries that correspond to real public calls, such as `scheduler_ns`, `module_link_ns`, `signature_verify_ns`, `filesystem_operation_ns`, or `canonicalization_ns`. A phase not exercised by a case is `None`, never `0`.

Each timing sample must also rerun `semantic_witness(case)` after timing and require equality with the pre-timing witness. This ensures the measurement path cannot silently change behavior.

- [ ] **Step 4: Separate allocation measurement from timing**

Use `tracemalloc` in a separate single execution after timing trials. Record `peak_memory_bytes`; do not include the tracemalloc run in timing samples. Record `source_bytes`, `ir_bytes`, and `receipt_bytes` where available; otherwise record `None`.

- [ ] **Step 5: Implement aggregation reliability**

Seven final samples follow two warmups. `aggregate_samples` returns `count`, `median`, `minimum`, `maximum`, `median_absolute_deviation`, and `relative_dispersion=(maximum-minimum)/max(median,1)`. Any primary timing metric above `0.20` relative dispersion marks the case `UNRELIABLE`.

- [ ] **Step 6: Seal the baseline receipt**

The run body contains exactly these top-level fields before `run_hash` is added:

```text
schema
status
mode
plan_hash
base_sha
base_tree
head_sha
head_tree
environment
benchmark_corpus_hash
adversarial_corpus_hash
metric_policy
hardening_summary
semantic_witnesses
benchmark_results
hotspot_classification
promotion_authority_bool
```

`promotion_authority_bool` is always false. `write_external_receipt_once` rejects any path inside the repository, rejects an existing file, creates with `O_CREAT|O_EXCL`, writes canonical JSON plus newline, flushes, and fsyncs.

- [ ] **Step 7: Run focal tests and commit**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance tests.test_v2_hardening_adversarial
git add tools/v2_hardening_corpus.py tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: measure sealed V2 hardening baseline"
```

Expected: PASS, zero skips.

---

### Task 5: Add comparison, hotspot classification, and the no-speculative-optimization gate

**Files:**
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces `compare_runs(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]`.
- Produces `classify_hotspots(run: Mapping[str, Any]) -> dict[str, Any]`.

- [ ] **Step 1: Write synthetic comparison tests**

Cover these exact rules:

```text
corpus mismatch                    REJECT
adversarial corpus mismatch        REJECT
environment fingerprint mismatch   REJECT
semantic witness mismatch          REJECT
hardening summary regression       REJECT
any primary case >5% slower        REJECT unless result declares exact explained case/metric
>=10% material improvement         IMPROVEMENT when all vetoes are clear
no >=10% improvement               NO_MATERIAL_CHANGE
no stable hotspot                  NO_OPTIMIZATION_JUSTIFIED
unreliable benchmark               UNRELIABLE_BASELINE
```

Test a 50% faster candidate with changed semantic witness and require `REJECT`.

- [ ] **Step 2: Run RED**

Expected: missing compare/classify APIs.

- [ ] **Step 3: Implement comparison vetoes before speed comparisons**

The first checks are exact equality of `benchmark_corpus_hash`, `adversarial_corpus_hash`, `environment.fingerprint_hash`, `semantic_witnesses`, and a no-regression hardening summary. Only after those pass may timing/memory ratios be evaluated.

- [ ] **Step 4: Implement hotspot classification**

A phase is a measured hotspot only when one named phase contributes at least 30% of measured case total in at least two scales of the same family. A scaling hotspot is also valid when the scale-1/2/3 ratios show repeatable superlinear growth in the same phase and all three measurements are reliable. Otherwise return `NO_OPTIMIZATION_JUSTIFIED`.

The classification record includes `status`, `family`, `phase`, `scale_evidence`, `contribution_ratios`, and `reasons`. For no-hotspot results, `family` and `phase` are `None`.

- [ ] **Step 5: Run GREEN and commit**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: gate V2 optimization on measured evidence"
```

Expected: PASS, zero skips.

---

### Task 6: Add the fail-closed CLI, certify infrastructure, and record the baseline

**Files:**
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`
- No baseline result file is committed.

**Interfaces:**
- CLI commands: `plan`, `hardening`, `baseline --receipt-out <external-new-path>`, `compare --baseline <external-file> --candidate <external-file>`.

- [ ] **Step 1: Write subprocess CLI tests**

Require `plan` READY only on the exact infrastructure frontier, `baseline` to reject an in-repo output path, `compare` to reject a tampered run receipt, and every successful command to print `PROMOTION_AUTHORITY=NO`.

- [ ] **Step 2: Run RED**

Expected: CLI parser/command failures.

- [ ] **Step 3: Implement bounded fail-closed CLI output**

On failure print:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=FAIL
PROMOTION_AUTHORITY=NO
```

On successful baseline print:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=PASS
HARDENING_CAMPAIGN=PASS
SEMANTIC_EQUIVALENCE_BASELINE=PASS
PERFORMANCE_BASELINE=RECORDED
PROMOTION_AUTHORITY=NO
```

Cap captured diagnostic output at 512 KiB. Subprocess timeouts must terminate the process tree and return non-zero.

- [ ] **Step 4: Run focal campaign tests**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance tests.test_v2_hardening_adversarial
```

Expected: PASS, zero skips.

- [ ] **Step 5: Prove semantic authority files are untouched**

```powershell
$Base = "2bdb047dcad41f9d112219bd65925c25668c02e0"
$Forbidden = @(
  "CANONICAL_INDEX.json",
  "spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json",
  "schemas/tev-script-v2-descriptor.schema.json",
  "schemas/tev-script-program-ir-v4.schema.json",
  "schemas/tev-script-v2-filesystem-artifacts.schema.json",
  "schemas/tev-script-v2-certify-full-receipt.schema.json",
  "tev_script/release_metadata_v2.py"
)
$Changed = @(git diff --name-only "$Base..HEAD")
$Touched = @($Forbidden | Where-Object { $Changed -contains $_ })
if ($Touched.Count -ne 0) { throw "SEMANTIC_AUTHORITY_DRIFT: $($Touched -join ',')" }
Write-Host "SEMANTIC_AUTHORITY_DRIFT=NO"
```

- [ ] **Step 6: Run full regression**

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

Expected: exit 0, `OK`, zero skips.

- [ ] **Step 7: Run stable-profile technical certification against current stable main**

```powershell
$Base = "2bdb047dcad41f9d112219bd65925c25668c02e0"
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Nonce = ([guid]::NewGuid().ToString("N")).Substring(0,8)
$Receipt = "C:\TEV\TEV-SCRIPT-V2-HARDENING-CERT-$Stamp-$Nonce.json"

& "C:\TEV\VENV\TEV-SCRIPT-V2-PHASE-T-20260815-084242-cbf5a015\Scripts\python.exe" `
  .\RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py `
  --profile stable `
  --expected-base $Base `
  --receipt-out $Receipt
```

Require `CERTIFY_V2=PASS`, `FULL_REGRESSION=PASS`, and `LANGUAGE_STABLE=NO`. This is technical certification only; no new Stable Admission is requested.

- [ ] **Step 8: Record the external baseline**

```powershell
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Nonce = ([guid]::NewGuid().ToString("N")).Substring(0,8)
$Baseline = "C:\TEV\TEV-SCRIPT-V2-HARDENING-BASELINE-$Stamp-$Nonce.json"
python .\tools\tevprober_v2_hardening_performance.py hardening
python .\tools\tevprober_v2_hardening_performance.py baseline --receipt-out $Baseline
```

Require:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=PASS
HARDENING_CAMPAIGN=PASS
SEMANTIC_EQUIVALENCE_BASELINE=PASS
PERFORMANCE_BASELINE=RECORDED
PROMOTION_AUTHORITY=NO
```

- [ ] **Step 9: Make the hotspot decision**

Accept only `HOTSPOT_CLASSIFICATION=MEASURED_HOTSPOT`, `HOTSPOT_CLASSIFICATION=NO_OPTIMIZATION_JUSTIFIED`, or `HOTSPOT_CLASSIFICATION=UNRELIABLE_BASELINE`.

If `UNRELIABLE_BASELINE`, stop and repair measurement reliability only. If `NO_OPTIMIZATION_JUSTIFIED`, finish the campaign infrastructure without implementation optimization. If `MEASURED_HOTSPOT`, record the exact family, phase, scale evidence, contribution ratios, baseline receipt hash, and implicated implementation files, then write a new focused design and TDD plan for exactly that hotspot.

- [ ] **Step 10: Commit the final CLI implementation after verification**

```powershell
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: expose V2 hardening performance probe"
```

Final infrastructure evidence must be:

```text
BASE_IDENTITY_BOUND=PASS
PLAN_HASH=PASS
BENCHMARK_CORPUS_HASH=PASS
HARDENING_CAMPAIGN=PASS
NEGATIVE_CONTROL_TAMPER=PASS
SEMANTIC_EQUIVALENCE_BASELINE=PASS
DETERMINISTIC_REPLAY=PASS
PERFORMANCE_BASELINE=RECORDED
PROMOTION_AUTHORITY=FALSE
HOTSPOT_CLASSIFICATION=<MEASURED_HOTSPOT|NO_OPTIMIZATION_JUSTIFIED>
```

Do not create a draft PR until the full technical certification and baseline evidence are both available.
