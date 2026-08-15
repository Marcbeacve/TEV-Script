# TEV Script V2.0.x Hardening + Performance — Design

Date: 2026-08-15

## Objective

Improve the already stable TEV Script V2 implementation without changing the V2 language contract.

This campaign is strictly V2.0.x maintenance. It may harden implementations, add adversarial evidence, add profiling/benchmark tooling, and optimize implementation hot paths only when the optimization is backed by measured evidence and preserves exact observable semantics.

The stable semantic authority remains the canonical V2 release on `main`:

```text
BASE_COMMIT=2bdb047dcad41f9d112219bd65925c25668c02e0
BASE_TREE=aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8
LANGUAGE_VERSION=2.0.0
STABLE_ADMISSION_RECEIPT_SHA256=4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6
```

The campaign must not reinterpret or rewrite this stable receipt. Any future stable maintenance release has its own Git identity and certification evidence.

## Non-negotiable semantic boundary

The following are frozen during this campaign unless a reproducible correctness defect proves that the stable contract itself is internally inconsistent, in which case this campaign stops and a separate language-evolution project is required:

- lexical grammar and parser acceptance/rejection semantics;
- static semantics and type rules;
- Program IR V4 schemas and operational meaning;
- portable value model and exact integer/rational semantics;
- capability ABI and explicit-effect rules;
- canonical JSON and hashing semantics;
- conformance receipt meaning;
- language version `2.0.0`;
- stable-admission authority model.

Implementation refactors are allowed only when the old and new versions are observationally equivalent for the governed V2 surface.

## Approaches considered

### A. Optimize obvious-looking code immediately

Rejected. It risks optimizing non-bottlenecks and creates semantic-risk churn without causal evidence.

### B. Add fuzzing only

Useful for hardening but insufficient. It can find correctness defects but does not tell us where runtime/compiler cost is concentrated.

### C. Evidence-first hardening + profiling + gated optimization — selected

1. Freeze a baseline against the exact stable commit.
2. Add a hash-sealed TEV-Script probing harness inspired by the TEVProber pattern.
3. Run adversarial campaigns against source, IR, manifests, capabilities, filesystem boundaries, and receipts.
4. Measure phase-level CPU time, wall time, peak memory, artifact size, and deterministic replay cost.
5. Rank hot paths from measured contribution.
6. Optimize one causal bottleneck at a time.
7. Require semantic-equivalence and security non-regression after every accepted optimization.

This approach preserves the stable contract while generating useful engineering evidence.

## TEVProber role

TEVProber is used as a design pattern, not as a runtime dependency of TEV Script.

The relevant pattern is:

```text
exact causal frontier
+ exact base identity
+ hash-sealed plan
+ bounded output
+ deterministic environment
+ finite selected tests/benchmarks
+ structural negative controls
+ no promotion authority
```

TEV Script will receive a local, repository-owned probe harness with no dependency on `TEVProver-CUOFC` or IA-TEV.

The probe harness is measurement authority only. It may never alter language authority or claim release/stable promotion.

## Campaign architecture

### 1. Baseline Manifest

A baseline runner records the exact stable baseline for a finite benchmark suite.

Required baseline identity:

```text
commit
 tree
python version
platform
processor count
benchmark corpus hash
probe-plan hash
```

Required metrics per case:

```text
parse_ns
static_analysis_ns
lowering_ns
ir_validation_ns
canonicalization_ns
execution_ns
receipt_ns
peak_memory_bytes
source_bytes
ir_bytes
receipt_bytes
```

Not every case exercises every phase; absent phases are recorded explicitly, never inferred as zero.

Measurements must use repeated trials, warm-up separation, deterministic inputs, and medians. Performance claims are invalid if the baseline and candidate are measured with different benchmark inputs or materially different environments.

### 2. Adversarial Hardening Campaign

The hardening campaign is finite, reproducible, and seed-bound.

Families:

#### Source boundary

- malformed UTF-8;
- truncated tokens;
- pathological whitespace/comment structure;
- deeply nested but bounded syntax;
- oversized identifiers/text within governed limits;
- invalid generic/protocol combinations;
- recursion-contract edge cases;
- deterministic task-DAG edge cases.

Expected result: deterministic accept or deterministic fail-closed diagnostic. No crash, hang, uncontrolled resource growth, or ambient I/O.

#### Program IR V4 boundary

- wrong schema/version;
- missing/extra fields;
- type-stack mismatches;
- malformed control flow;
- duplicate/colliding canonical identifiers;
- budget manipulation;
- artifact hash tampering;
- recursive-profile contract tampering.

Expected result: validator rejects before execution where required.

#### Capability/effect boundary

- missing capability;
- extra ungranted capability;
- observation transcript mismatch;
- effect intent tampering;
- effect replay/double-commit attempt;
- provider response mismatch;
- capability argument/result type mismatch.

Expected result: fail closed with no implicit physical effect.

#### Filesystem boundary

- traversal attempts;
- symlink/reparse substitution;
- root identity replacement;
- path race/TOCTOU attempts;
- oversized reads;
- replace races;
- unsupported secure primitive simulation.

Expected result: existing V2 security invariants remain intact.

#### Remote module/signature boundary

- invalid Ed25519 signature;
- wrong public-key pin;
- envelope rehash without valid signature;
- manifest/body hash mismatch;
- transport pin mismatch;
- bundle extraction path attacks.

Expected result: fail closed before untrusted module execution.

#### Receipt/canonicalization boundary

- field reordering;
- field insertion/removal;
- number/string substitution;
- hash substitution;
- alternate Unicode encodings;
- receipt identity mismatch.

Expected result: exact canonical validation and hash mismatch rejection.

### 3. Performance Corpus

The initial corpus is intentionally small and structural rather than application-specific.

Case families:

1. tiny pure program;
2. collection-heavy pure program;
3. generic specialization pressure;
4. protocol/associated-type pressure;
5. bounded-recursion pressure;
6. wide task DAG;
7. deep deterministic task DAG within limits;
8. observation-heavy program;
9. effect-plan-heavy program;
10. local multi-module bundle;
11. signed remote module bundle using local/offline transport fixture;
12. filesystem read workload;
13. filesystem replace workload;
14. canonicalization/receipt-heavy synthetic workload.

Each family includes at least three fixed scales where meaningful. The corpus is checked into the repository or deterministically generated from a sealed seed.

### 4. Optimization Gate

No optimization is accepted merely because one timing improves.

For a candidate change, require:

```text
SEMANTIC_EQUIVALENCE=PASS
CANONICAL_IR_COMPATIBILITY=PASS
V2_CONFORMANCE=PASS
V1_NON_REGRESSION=PASS
SECURITY_NEGATIVES=PASS
DETERMINISTIC_REPLAY=PASS
```

And at least one material measured improvement:

```text
median wall time improves >= 10%
or
peak memory improves >= 10%
or
IR/artifact size improves >= 10%
or
an identified superlinear slope is reduced materially
```

A smaller improvement may be accepted only if it removes a proven pathological scaling regime or correctness/resource hazard.

Regressions are bounded:

- no governed benchmark may regress >5% median without explicit causal explanation;
- no memory benchmark may regress >5% without compensating evidence;
- no security or semantic gate may regress at all.

Performance noise is handled by repeated measurements and confidence/dispersion reporting; a single run is not sufficient evidence.

### 5. Semantic Equivalence Strategy

The preferred equivalence proof is artifact-level rather than source-text-level.

For unchanged source inputs:

- parser/static outcome class must match;
- successful compilation must produce canonical Program IR V4 with identical semantic content;
- canonical hashes must remain identical unless a non-semantic receipt field is explicitly designed to differ;
- execution output/state/events/observations/effect plans must match;
- replay from the same transcript must match;
- rejected inputs must remain rejected with the same governed error code class where error-code stability is part of the contract.

If an optimization intentionally changes a non-semantic diagnostic string or internal ordering, tests must prove the canonical contract is unchanged.

## TEV-Script probe harness

Proposed repository-owned tooling:

```text
tools/tevprober_v2_hardening_performance.py
benchmarks/v2/...
tests/test_tevprober_v2_hardening_performance.py
```

The harness plan contains:

```text
schema
base_sha
base_tree
mode
changed_paths
benchmark_ids
adversarial_campaign_ids
metric_policy
semantic_equivalence_policy
negative_controls
promotion_authority=false
plan_hash
```

The run receipt contains:

```text
plan_hash
exact Git identity
environment fingerprint
benchmark corpus hash
per-case raw aggregates
hardening results
semantic-equivalence result
performance comparison
candidate classification
run_hash
```

The harness must refuse unknown changed paths outside its declared causal frontier when running a focused optimization experiment.

## Profiling policy

Start with low-intrusion instrumentation:

- `time.perf_counter_ns()` at explicit phase boundaries;
- `tracemalloc` for Python allocation peaks where reliable;
- process RSS sampling only as supplementary evidence;
- serialized benchmark execution by default;
- GC policy recorded and kept consistent between baseline/candidate;
- no profiler active during final timing numbers unless profiler overhead is explicitly measured.

Use `cProfile` or equivalent only to locate candidate functions after a phase-level hotspot is established. Profiling output is diagnostic evidence, not the benchmark result itself.

## Optimization priorities

Optimization candidates are selected by measured impact, not intuition. Likely categories to investigate only if the baseline points there:

- repeated canonical serialization/hashing;
- repeated schema validation setup;
- redundant AST/type traversal;
- generic monomorphization cacheability;
- repeated Program IR normalization/validation;
- module graph recomputation;
- deterministic task scheduler bookkeeping;
- transcript/receipt canonicalization;
- filesystem path/security check duplication that can be safely shared without weakening TOCTOU guarantees.

Security checks are never removed for speed. Any caching of security-sensitive results must prove its authority lifetime and invalidation model.

## Fail-closed rules

The campaign itself must fail closed when:

- baseline Git identity is not the expected stable base;
- worktree identity cannot be read;
- benchmark corpus hash changes unexpectedly;
- plan hash is invalid;
- environment fingerprint is incompatible for comparison;
- candidate changes semantic-authority files without explicit campaign HOLD;
- any semantic/security regression appears;
- benchmark output is incomplete or ambiguous;
- a benchmark times out;
- measurement dispersion exceeds the configured reliability threshold.

## Repository workflow

Campaign branch:

```text
agent/tev-script-v2-hardening-performance-v1
```

Base:

```text
2bdb047dcad41f9d112219bd65925c25668c02e0
```

Workflow:

```text
baseline evidence
-> hardening/probe tooling
-> focal certification
-> identify bottleneck
-> one optimization
-> compare to baseline
-> full regression/certification
-> draft PR
```

No merge, tag, release, stable promotion, or update to `main` without explicit authorization.

## Definition of Done — campaign infrastructure

The infrastructure phase is complete only when it can produce a sealed baseline and detect intentional negative controls:

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
```

## Definition of Done — accepted optimization

An optimization is accepted only when:

```text
ROOT_CAUSE_HOTSPOT=MEASURED
OPTIMIZATION_CAUSAL_LINK=PASS
SEMANTIC_EQUIVALENCE=PASS
CANONICAL_IR_COMPATIBILITY=PASS
V2_CONFORMANCE=PASS
V1_NON_REGRESSION=PASS
SECURITY_NEGATIVES=PASS
DETERMINISTIC_REPLAY=PASS
PERFORMANCE_IMPROVEMENT=PASS
FULL_REGRESSION=PASS
REPO_CLEAN_AFTER_CERTIFICATION=PASS
```

The campaign may legitimately finish with `NO_OPTIMIZATION_JUSTIFIED` if the baseline shows no material bottleneck worth changing. That is a valid result, preferable to speculative complexity.
