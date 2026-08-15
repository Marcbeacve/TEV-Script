# TEV Script V2.0.x Hardening + Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, hash-sealed hardening and performance harness for stable TEV Script V2.0.0, record a trustworthy baseline, and decide from measured evidence whether any implementation optimization is justified without changing V2 semantics.

**Architecture:** Add repository-owned tooling outside the V2 semantic-authority surface. `tools/v2_hardening_corpus.py` owns deterministic benchmark/adversarial case construction and execution adapters; `tools/tevprober_v2_hardening_performance.py` owns Git identity, plan sealing, measurement, comparison, receipts, and CLI orchestration. New tests import only these `tools/` modules so the stable V2 feature matrix does not need to change merely to enumerate campaign tests.

**Tech Stack:** Python 3.11+ standard library only for campaign code (`dataclasses`, `hashlib`, `hmac`, `json`, `statistics`, `subprocess`, `tempfile`, `time`, `tracemalloc`); existing TEV Script V2 Python implementation; `unittest`; canonical SHA-256; external JSON receipts. No new runtime dependency and no GitHub Actions.

## Global Constraints

- Stable semantic base is exactly `2bdb047dcad41f9d112219bd65925c25668c02e0` with tree `aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8`.
- Stable Admission receipt authority remains `4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6`; this campaign never rewrites or reinterprets it.
- Language version remains exactly `2.0.0`.
- Do not modify grammar, parser acceptance/rejection semantics, static semantics, Program IR V4 schema/meaning, portable value model, capability ABI, canonical hashing, conformance receipt meaning, or stable-admission authority.
- Do not modify `CANONICAL_INDEX.json`, `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`, V2 schemas, or `tev_script/release_metadata_v2.py` in the infrastructure phase.
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
- `tools/v2_hardening_corpus.py` — deterministic benchmark/adversarial case definitions, corpus hashing, and implementation adapters.
- `tools/tevprober_v2_hardening_performance.py` — exact Git/frontier policy, sealed plans, measurement engine, hardening runner, comparison gate, external receipts, CLI.
- `tests/test_tevprober_v2_hardening_performance.py` — probe/frontier/sealing/measurement/comparison/CLI regression tests; imports only `tools.*`.
- `tests/test_v2_hardening_adversarial.py` — deterministic finite adversarial campaign tests through `tools.v2_hardening_corpus`; imports no governed `tev_script.*` module directly.

**Already present and changed on this campaign branch:**
- `docs/superpowers/specs/2026-08-15-tev-script-v2-hardening-performance-design.md` — approved design.
- `docs/superpowers/plans/2026-08-15-tev-script-v2-hardening-performance.md` — this implementation plan.

**Must remain unchanged in this infrastructure plan:**
- `CANONICAL_INDEX.json`
- `spec/TEV_SCRIPT_V2_FEATURE_MATRIX.json`
- `schemas/tev-script-v2-*.json`
- `schemas/tev-script-program-ir-v4.schema.json`
- `tev_script/release_metadata_v2.py`
- parser/compiler/runtime implementation files under `tev_script/`

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
- No function in this task executes benchmarks or claims release authority.

- [ ] **Step 1: Write failing contract tests**

Add tests that import only `tools.tevprober_v2_hardening_performance` and assert exact constants, exact frontier acceptance, unknown-path HOLD, tamper rejection, path normalization rejection, and `promotion_authority_bool is False`.

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
    def test_exact_infrastructure_frontier_is_ready_and_non_promotional(self) -> None:
        value = probe.plan(EXPECTED_FRONTIER)
        self.assertEqual(value["status"], "READY")
        self.assertEqual(tuple(value["changed_paths"]), EXPECTED_FRONTIER)
        self.assertEqual(value["base_sha"], "2bdb047dcad41f9d112219bd65925c25668c02e0")
        self.assertEqual(value["base_tree"], "aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8")
        self.assertIs(value["promotion_authority_bool"], False)
        self.assertTrue(probe.verify_plan(value))

    def test_unknown_path_holds(self) -> None:
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

Run:

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: import failure because `tools/tevprober_v2_hardening_performance.py` does not yet exist.

- [ ] **Step 3: Implement the minimal sealed plan**

Use only standard-library canonical JSON. The plan must be reproducible and must not trust unordered caller input.

```python
from __future__ import annotations

import hashlib
import hmac
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

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


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return "sha256:" + hashlib.sha256(_canonical_bytes(value)).hexdigest()


def normalize_paths(values: Sequence[str]) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError("tevprober_paths_sequence_required")
    normalized: list[str] = []
    for raw in values:
        value = str(raw).strip().replace("\\", "/").removeprefix("./")
        if not value or value.startswith(("/", "../")) or "/../" in value or "\x00" in value or "\n" in value:
            raise ValueError("tevprober_path_invalid")
        normalized.append(value)
    return tuple(sorted(dict.fromkeys(normalized)))


def plan(changed_paths: Sequence[str]) -> dict[str, Any]:
    changed = normalize_paths(changed_paths)
    expected = set(INFRASTRUCTURE_FRONTIER)
    observed = set(changed)
    unknown = sorted(observed - expected)
    missing = sorted(expected - observed)
    ready = not unknown and not missing
    body = {
        "schema": PLAN_SCHEMA,
        "status": "READY" if ready else "HOLD",
        "mode": "INFRASTRUCTURE_BASELINE" if ready else "HOLD",
        "base_sha": BASE_SHA,
        "base_tree": BASE_TREE,
        "changed_paths": list(changed),
        "metric_policy": dict(METRIC_POLICY),
        "reasons": (
            ["exact_infrastructure_frontier", "stable_base_bound", "non_semantic_campaign", "promotion_forbidden"]
            if ready
            else [*(f"out_of_frontier:{x}" for x in unknown), *(f"missing_frontier:{x}" for x in missing)]
        ),
        "promotion_authority_bool": False,
        "semantic_authority_change_bool": False,
    }
    return {**body, "plan_hash": _sha256(body)}
```

Implement `verify_plan` by rebuilding `plan(value["changed_paths"])`, comparing the exact canonical bytes and the hash with `hmac.compare_digest`. Implement `resolve_changed_paths` from `git diff --name-only BASE_SHA...HEAD` plus `git status --porcelain=v1 --untracked-files=all`. Implement `environment_fingerprint` with Python version, implementation, OS, machine, CPU count, and a hash of those stable fields; do not include wall-clock time.

- [ ] **Step 4: Run GREEN**

Run the same unittest command. Expected: PASS, zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "test: seal V2 hardening probe contract"
```

---

### Task 2: Add the deterministic benchmark corpus and semantic witness adapter

**Files:**
- Create: `tools/v2_hardening_corpus.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces immutable `BenchmarkCaseV2`.
- Produces `build_benchmark_corpus() -> tuple[BenchmarkCaseV2, ...]`.
- Produces `benchmark_corpus_hash() -> str`.
- Produces `semantic_witness(case: BenchmarkCaseV2) -> dict[str, Any]`.
- `semantic_witness` is the only campaign adapter allowed to call governed TEV Script V2 APIs for benchmark cases.

- [ ] **Step 1: Write corpus determinism and semantic-witness tests**

Tests continue to import only the `tools` module:

```python
from tools import v2_hardening_corpus as corpus


def test_corpus_is_closed_and_hash_stable(self) -> None:
    cases = corpus.build_benchmark_corpus()
    self.assertEqual(len(cases), 42)
    self.assertEqual(len({case.case_id for case in cases}), 42)
    self.assertEqual({case.scale for case in cases}, {1, 2, 3})
    self.assertEqual(
        {case.family for case in cases},
        {
            "tiny_pure",
            "collection_heavy",
            "generic_specialization",
            "protocol_associated_type",
            "bounded_recursion",
            "wide_task_dag",
            "deep_task_dag",
            "observation_heavy",
            "effect_plan_heavy",
            "local_module_bundle",
            "signed_remote_module_bundle",
            "filesystem_read",
            "filesystem_replace",
            "canonical_receipt_heavy",
        },
    )
    self.assertEqual(corpus.benchmark_corpus_hash(), corpus.benchmark_corpus_hash())


def test_tiny_pure_witness_is_deterministic(self) -> None:
    case = next(x for x in corpus.build_benchmark_corpus() if x.case_id == "tiny_pure.s1")
    left = corpus.semantic_witness(case)
    right = corpus.semantic_witness(case)
    self.assertEqual(left, right)
    self.assertEqual(left["language_version"], "2.0.0")
    self.assertEqual(left["profile"], "pure")
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: import failure for `tools.v2_hardening_corpus`.

- [ ] **Step 3: Implement the corpus data model and closed 14×3 inventory**

Use a plain-data case model so the corpus itself is hashable and independent of Python function identities:

```python
from dataclasses import asdict, dataclass
from typing import Any

@dataclass(frozen=True, slots=True)
class BenchmarkCaseV2:
    case_id: str
    family: str
    scale: int
    kind: str
    payload: dict[str, Any]


def build_benchmark_corpus() -> tuple[BenchmarkCaseV2, ...]:
    cases: list[BenchmarkCaseV2] = []
    for scale in (1, 2, 3):
        cases.extend(
            (
                BenchmarkCaseV2(
                    f"tiny_pure.s{scale}", "tiny_pure", scale, "source_pure",
                    {"source": f'script P{scale} version "2.0.0"; fn add(x:Int)->Int=x+{scale}; entry main:Int=add(41);'},
                ),
                BenchmarkCaseV2(
                    f"bounded_recursion.s{scale}", "bounded_recursion", scale, "source_recursive",
                    {"n": 3 + scale, "max_depth": 8 + scale},
                ),
                BenchmarkCaseV2(
                    f"wide_task_dag.s{scale}", "wide_task_dag", scale, "task_scheduler",
                    {"width": 2 ** (scale + 1), "workers": min(4, 2 ** (scale + 1))},
                ),
                BenchmarkCaseV2(
                    f"canonical_receipt_heavy.s{scale}", "canonical_receipt_heavy", scale, "canonical",
                    {"records": 32 * scale},
                ),
            )
        )
    # Add the remaining ten families with exactly one case per scale using the
    # same explicit constructor form; do not generate family names dynamically.
    ...
```

Do **not** leave the ellipsis in implementation. The final tuple must contain exactly the 14 family names asserted by the test, each at scales 1/2/3, and `case_id` must be `<family>.s<scale>`.

For source-based payloads, generate finite source text deterministically from `scale`. For filesystem and signed-module cases, payloads contain only counts/sizes/fixture identifiers; the adapter creates all temporary files/directories at execution time. No benchmark case stores absolute paths.

`benchmark_corpus_hash()` is SHA-256 over canonical JSON of `[asdict(case) ...]`.

- [ ] **Step 4: Implement semantic witnesses using existing V2 APIs**

For `source_pure`, use the already-governed path exercised by `tests/test_program_ir_v4.py`:

```python
from tev_script.program_ir_v4 import (
    canonical_program_ir_v4_bytes,
    export_program_ir_v4_pure,
    run_program_ir_v4_pure,
    validate_program_ir_v4_pure,
)
from tev_script.source_program_v2 import compile_and_run_program_v2, compile_program_v2


def _pure_witness(source: str) -> dict[str, Any]:
    compiled, source_receipt = compile_and_run_program_v2(source)
    ir = export_program_ir_v4_pure(compiled)
    validation = validate_program_ir_v4_pure(ir)
    portable_receipt = run_program_ir_v4_pure(ir)
    wire = canonical_program_ir_v4_bytes(ir)
    if portable_receipt.result_hash != source_receipt.result_hash:
        raise RuntimeError("tevprober_source_ir_result_divergence")
    return {
        "language_version": compiled.language_version,
        "profile": "pure",
        "semantic_hash": compiled.semantic_hash,
        "program_ir_hash": validation.program_ir_hash,
        "result_hash": portable_receipt.result_hash,
        "receipt_hash": portable_receipt.receipt_hash,
        "ir_bytes": len(wire),
    }
```

Add explicit adapters for recursive, task-scheduler, effects/observation, local module, signed remote module, filesystem read/replace, and canonical-only case kinds by reusing their existing public/tested APIs. Every adapter returns plain canonicalizable data only; no object repr, memory address, temporary path, or timing value belongs in a semantic witness.

- [ ] **Step 5: Run GREEN and repeatability check**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
python -c "from tools.v2_hardening_corpus import benchmark_corpus_hash; print(benchmark_corpus_hash()); print(benchmark_corpus_hash())"
```

Expected: tests PASS and the two printed hashes are byte-identical.

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
- Produces immutable `AdversarialCaseV2`.
- Produces `build_adversarial_cases() -> tuple[AdversarialCaseV2, ...]`.
- Produces `adversarial_corpus_hash() -> str`.
- Produces `run_adversarial_case(case: AdversarialCaseV2) -> dict[str, Any]`.
- Each result contains `case_id`, `family`, `status`, `expected_outcome`, and either a governed diagnostic code or a deterministic success witness.

- [ ] **Step 1: Write finite-campaign tests**

`tests/test_v2_hardening_adversarial.py` imports only `tools.v2_hardening_corpus`:

```python
from __future__ import annotations

import unittest
from tools import v2_hardening_corpus as corpus


class V2AdversarialCampaignTests(unittest.TestCase):
    def test_campaign_is_closed_deterministic_and_fail_closed(self) -> None:
        cases = corpus.build_adversarial_cases()
        self.assertGreaterEqual(len(cases), 48)
        self.assertEqual(len(cases), len({case.case_id for case in cases}))
        first = [corpus.run_adversarial_case(case) for case in cases]
        second = [corpus.run_adversarial_case(case) for case in cases]
        self.assertEqual(first, second)
        self.assertTrue(all(item["status"] == "PASS" for item in first))

    def test_adversarial_corpus_hash_is_stable(self) -> None:
        self.assertEqual(corpus.adversarial_corpus_hash(), corpus.adversarial_corpus_hash())
```

- [ ] **Step 2: Run RED**

```powershell
python -m unittest -v tests.test_v2_hardening_adversarial
```

Expected: missing adversarial API failures.

- [ ] **Step 3: Define at least 48 explicit cases across six families**

Use eight or more cases in each family:

```text
source
program_ir_v4
capability_effect
filesystem
remote_module_signature
receipt_canonicalization
```

The case model is plain data:

```python
@dataclass(frozen=True, slots=True)
class AdversarialCaseV2:
    case_id: str
    family: str
    mutation: str
    expected_outcome: str
    expected_diagnostic_codes: tuple[str, ...]
```

Required explicit mutations include:

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

Reuse existing implementation APIs and temporary local fixtures. A case passes only when the observed governed rejection/success class matches its predeclared expectation. Catch only `TevScriptError` or the exact documented validation exception for that boundary; unexpected exceptions are campaign failures, not successful rejection.

- [ ] **Step 4: Run GREEN twice**

```powershell
python -m unittest -v tests.test_v2_hardening_adversarial
python -m unittest -v tests.test_v2_hardening_adversarial
```

Expected: both runs PASS with identical case count and zero skips.

- [ ] **Step 5: Commit**

```powershell
git add tools/v2_hardening_corpus.py tests/test_v2_hardening_adversarial.py
git commit -m "test: add finite V2 adversarial campaign"
```

---

### Task 4: Add phase-level measurement and a self-hashed external baseline receipt

**Files:**
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tools/v2_hardening_corpus.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- `tools.v2_hardening_corpus.measure_once(case: BenchmarkCaseV2) -> dict[str, int | None]` returns phase metrics plus semantic witness.
- `measure_case(case, *, warmups: int = 2, trials: int = 7) -> dict[str, Any]`.
- `run_baseline(probe: Mapping[str, Any]) -> dict[str, Any]`.
- `write_external_receipt_once(path: Path, receipt: Mapping[str, Any]) -> Path`.

- [ ] **Step 1: Write aggregation/receipt tests before timing implementation**

Use synthetic samples for median/dispersion logic so tests do not depend on machine speed:

```python
def test_metric_aggregate_uses_median_and_reports_dispersion(self) -> None:
    value = probe.aggregate_samples([100, 101, 99, 100, 100, 102, 98])
    self.assertEqual(value["median"], 100)
    self.assertEqual(value["minimum"], 98)
    self.assertEqual(value["maximum"], 102)
    self.assertLess(value["relative_dispersion"], 0.05)


def test_run_receipt_self_hash_detects_tamper(self) -> None:
    receipt = probe._seal_run({"schema": probe.RUN_SCHEMA, "status": "PASS"})
    self.assertTrue(probe.verify_run_receipt(receipt))
    tampered = dict(receipt)
    tampered["status"] = "FAIL"
    self.assertFalse(probe.verify_run_receipt(tampered))
```

- [ ] **Step 2: Run RED**

Run the focal probe test module. Expected: missing aggregation/run APIs.

- [ ] **Step 3: Implement explicit phase measurements**

`measure_once` measures only phase boundaries owned by the adapter. For pure-source cases split at least:

```python
start = time.perf_counter_ns()
parsed = parse_program_v2(source)
parse_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
compiled = compile_parsed_program_v2(parsed)
static_analysis_and_lowering_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
ir = export_program_ir_v4_pure(compiled)
lowering_export_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
validation = validate_program_ir_v4_pure(ir)
ir_validation_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
wire = canonical_program_ir_v4_bytes(ir)
canonicalization_ns = time.perf_counter_ns() - start

start = time.perf_counter_ns()
receipt = run_program_ir_v4_pure(ir)
execution_and_receipt_ns = time.perf_counter_ns() - start
```

Where an API does not expose a clean internal phase boundary, record one combined named metric rather than estimating sub-phases. Missing phases are `None`, never zero.

For peak allocations, start `tracemalloc` immediately before one measured iteration, reset peak, run the case, capture `get_traced_memory()[1]`, and stop tracing. Timing trials and allocation trials are separate so tracemalloc overhead does not contaminate final wall-time numbers.

- [ ] **Step 4: Implement robust aggregation**

Use seven final trials after two warmups. `aggregate_samples` returns count, median, minimum, maximum, median absolute deviation, and `relative_dispersion = (maximum-minimum)/max(median,1)`. If any required metric exceeds `METRIC_POLICY["max_relative_dispersion"]`, classify the benchmark run `UNRELIABLE` rather than pretending an improvement.

- [ ] **Step 5: Build and verify the sealed baseline receipt**

The baseline body includes:

```text
schema
status
mode=BASELINE
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
promotion_authority_bool=false
```

Seal it as `run_hash = sha256(canonical body)`. `write_external_receipt_once` must reject paths inside the repo, reject pre-existing output, create once with `O_CREAT|O_EXCL`, flush and fsync.

- [ ] **Step 6: Run focal tests**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance tests.test_v2_hardening_adversarial
```

Expected: PASS, zero skips.

- [ ] **Step 7: Commit**

```powershell
git add tools/tevprober_v2_hardening_performance.py tools/v2_hardening_corpus.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: measure sealed V2 hardening baseline"
```

---

### Task 5: Add baseline/candidate comparison and the no-speculative-optimization gate

**Files:**
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- Produces `compare_runs(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]`.
- Produces `classify_hotspots(run: Mapping[str, Any]) -> dict[str, Any]`.
- No comparison result has promotion authority.

- [ ] **Step 1: Add synthetic comparison tests**

Cover exact-corpus/environment requirements, 10% material improvement, 5% unexplained regression cap, semantic mismatch veto, and the valid `NO_OPTIMIZATION_JUSTIFIED` result.

```python
def test_semantic_mismatch_vetoes_fast_candidate(self) -> None:
    baseline = self.synthetic_run(total_ns=1000, semantic="A")
    candidate = self.synthetic_run(total_ns=500, semantic="B")
    result = probe.compare_runs(baseline, candidate)
    self.assertEqual(result["status"], "REJECT")
    self.assertIn("semantic_witness_mismatch", result["reasons"])


def test_ten_percent_improvement_passes_when_no_case_regresses_over_five_percent(self) -> None:
    baseline = self.synthetic_run(total_ns=1000, semantic="A")
    candidate = self.synthetic_run(total_ns=890, semantic="A")
    result = probe.compare_runs(baseline, candidate)
    self.assertEqual(result["status"], "IMPROVEMENT")
```

- [ ] **Step 2: Run RED**

Expected: missing compare/classify APIs.

- [ ] **Step 3: Implement strict comparison invariants**

Before comparing performance require:

```python
if baseline["benchmark_corpus_hash"] != candidate["benchmark_corpus_hash"]:
    return reject("benchmark_corpus_mismatch")
if baseline["adversarial_corpus_hash"] != candidate["adversarial_corpus_hash"]:
    return reject("adversarial_corpus_mismatch")
if baseline["environment"]["fingerprint_hash"] != candidate["environment"]["fingerprint_hash"]:
    return reject("environment_mismatch")
if baseline["semantic_witnesses"] != candidate["semantic_witnesses"]:
    return reject("semantic_witness_mismatch")
if baseline["hardening_summary"] != candidate["hardening_summary"]:
    return reject("hardening_regression")
```

Then compare medians per case/metric. A candidate is `IMPROVEMENT` only when at least one declared primary metric improves by `>= 10%`, no governed case has unexplained median regression `> 5%`, and no reliability gate is `UNRELIABLE`. Otherwise return `NO_OPTIMIZATION_JUSTIFIED`, `NO_MATERIAL_CHANGE`, or `REJECT` with explicit reasons.

- [ ] **Step 4: Implement hotspot classification without guessing**

For each case, compute contribution ratios from named phase medians to measured case total. Report a hotspot only when one phase contributes at least 30% of the case total in at least two scales of the same family, or when scale 1→2→3 growth demonstrates a repeatable superlinear regime. Otherwise the global classification is `NO_OPTIMIZATION_JUSTIFIED`.

- [ ] **Step 5: Run GREEN**

```powershell
python -m unittest -v tests.test_tevprober_v2_hardening_performance
```

Expected: PASS, zero skips.

- [ ] **Step 6: Commit**

```powershell
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: gate V2 optimization on measured evidence"
```

---

### Task 6: Add the fail-closed CLI and certify campaign infrastructure

**Files:**
- Modify: `tools/tevprober_v2_hardening_performance.py`
- Modify: `tests/test_tevprober_v2_hardening_performance.py`

**Interfaces:**
- CLI commands:
  - `plan`
  - `hardening`
  - `baseline --receipt-out <external-new-path>`
  - `compare --baseline <external-file> --candidate <external-file>`
- CLI never writes inside the repository and never mutates Git refs.

- [ ] **Step 1: Add subprocess CLI tests**

Test that `plan` reports READY only on the exact infrastructure frontier, `baseline` rejects an in-repo receipt path, `compare` rejects tampered receipts, and every successful command prints `PROMOTION_AUTHORITY=NO`.

- [ ] **Step 2: Run RED**

Expected: CLI argument/parser failures.

- [ ] **Step 3: Implement CLI with bounded output**

Use `argparse`. On failure print a stable first-line marker and return non-zero:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=FAIL
PROMOTION_AUTHORITY=NO
```

On successful infrastructure/baseline run print:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=PASS
HARDENING_CAMPAIGN=PASS
SEMANTIC_EQUIVALENCE_BASELINE=PASS
PERFORMANCE_BASELINE=RECORDED
PROMOTION_AUTHORITY=NO
```

Do not print unbounded source/IR/receipt bodies. Cap diagnostic stdout/stderr snippets at 512 KiB and kill timed-out subprocesses/process groups fail-closed.

- [ ] **Step 4: Run campaign focal tests**

```powershell
python -m unittest -v `
  tests.test_tevprober_v2_hardening_performance `
  tests.test_v2_hardening_adversarial
```

Expected: PASS, zero skips.

- [ ] **Step 5: Prove stable semantic authority files are unchanged**

Run:

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

Expected: `SEMANTIC_AUTHORITY_DRIFT=NO`.

- [ ] **Step 6: Run the full repository regression**

```powershell
python -m unittest discover -s tests -p "test*.py" -v
```

Expected: exit 0, `OK`, zero skips.

- [ ] **Step 7: Run stable-profile V2 technical certification against the current stable main**

Use the dedicated certification Python that already has certification tooling installed. The branch must be clean and `origin/main` must still equal the stable base.

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

Expected terminal witnesses include `CERTIFY_V2=PASS`, `FULL_REGRESSION=PASS`, and `LANGUAGE_STABLE=NO` because this is technical certification, not a new Stable Admission.

- [ ] **Step 8: Commit the CLI only after the full verification remains green**

```powershell
git add tools/tevprober_v2_hardening_performance.py tests/test_tevprober_v2_hardening_performance.py
git commit -m "feat: expose V2 hardening performance probe"
```

---

### Task 7: Record the stable baseline and make the hotspot decision

**Files:**
- No repository file is created for baseline results; receipt is external.
- No implementation optimization is authorized in this task.

**Interfaces:**
- Consumes the final `plan()` hash and exact campaign tooling identity.
- Produces one external self-hashed baseline receipt and one hotspot classification.

- [ ] **Step 1: Ensure exact clean campaign identity and current main base**

```powershell
if (@(git status --porcelain).Count -ne 0) { throw "dirty worktree" }
git fetch origin main --prune
$Base = "2bdb047dcad41f9d112219bd65925c25668c02e0"
if ((git rev-parse origin/main).Trim() -ne $Base) { throw "origin/main drift" }
```

- [ ] **Step 2: Run the sealed hardening campaign**

```powershell
python .\tools\tevprober_v2_hardening_performance.py hardening
```

Require:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=PASS
HARDENING_CAMPAIGN=PASS
PROMOTION_AUTHORITY=NO
```

- [ ] **Step 3: Record a fresh external baseline**

```powershell
$Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$Nonce = ([guid]::NewGuid().ToString("N")).Substring(0,8)
$Baseline = "C:\TEV\TEV-SCRIPT-V2-HARDENING-BASELINE-$Stamp-$Nonce.json"
python .\tools\tevprober_v2_hardening_performance.py baseline --receipt-out $Baseline
```

Require:

```text
TEV_SCRIPT_V2_HARDENING_PERFORMANCE=PASS
SEMANTIC_EQUIVALENCE_BASELINE=PASS
PERFORMANCE_BASELINE=RECORDED
PROMOTION_AUTHORITY=NO
```

- [ ] **Step 4: Classify hotspots from the sealed baseline**

The baseline command prints a bounded summary containing `HOTSPOT_CLASSIFICATION=<value>`. Accept only:

```text
MEASURED_HOTSPOT
NO_OPTIMIZATION_JUSTIFIED
UNRELIABLE_BASELINE
```

If `UNRELIABLE_BASELINE`, stop and repair measurement reliability only; do not optimize implementation code.

If `NO_OPTIMIZATION_JUSTIFIED`, the campaign may end successfully with no runtime/compiler modification.

If `MEASURED_HOTSPOT`, record the exact family, phase, contribution ratios, scaling evidence, baseline receipt hash, and candidate implementation files implicated. Then create a **new focused design/spec and TDD implementation plan** for exactly that hotspot. Do not optimize anything under this infrastructure plan.

- [ ] **Step 5: Final infrastructure status**

Report exactly the evidence available:

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

Do not create a draft PR until this status and the full technical certification are both available.
