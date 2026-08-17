# TEVScript Platform Completion — Design

Date: 2026-08-17
Status: APPROVED DESIGN / IMPLEMENTATION AUTHORIZED BY OPERATOR
Base: `main=c20718ddb2223ba0bfd05ff59006ca31e2966b0b`
Base tree: `812b140c5e6fb7232ef379773d9c37e8f3459f4c`
Stable predecessor: `TEVScript MAX 3.1.0 — Total-Core`
Target: close the language/platform around the already-published 3.1.0 core without weakening determinism, capability safety, exact arithmetic, bounded execution, or runtime independence.

## 1. Objective

The 3.1.0 semantic and runtime core is already published and admitted. This intervention does not add a competing language kernel. It closes the platform obligations required to make 3.1.x a coherent, externally implementable, falsifiable and reproducibly releasable language platform.

The closure relation is:

```text
3.1.0 semantic core
    + canonical version identity
    + normative 3.1 platform specification
    + explicit Language/IR/Runtime/ABI compatibility matrix
    + version-aware tooling contract
    + normative cross-runtime conformance corpus
    + deterministic property/differential fuzz harness
    + constitutional invariant gate
    + reproducible-release/provenance contract
    = TEVScript platform completion candidate
```

## 2. Hard invariants

1. `v3.1.0`, release commit `c20718dd...`, release tree `812b140c...` and its published wheel bytes remain immutable predecessor authority.
2. No runtime is a semantic authority. Language/specification, canonical schemas, static semantics, IR/value model, ABI and conformance receipts remain authoritative.
3. No production runtime interprets `.tevs` source.
4. No new implicit physical effect is introduced. Every physical effect still crosses an explicit capability/provider boundary.
5. Integer/rational exactness is preserved until an explicit host capability converts it.
6. Missing capabilities, malformed IR, exhausted budgets, incompatible profiles and identity mismatches fail closed.
7. `.tev` and `.tevg` remain external workflow kernels and are not copied into TEVScript.
8. Legacy V1/V2/V3 surfaces are preserved as compatibility surfaces unless an explicit version matrix marks them historical; this closure does not silently reinterpret them.
9. No GitHub Actions are introduced. Certification remains local/external-receipt driven.
10. Stable promotion, release, tagging and merge remain outside this branch and require explicit operator authorization.

## 3. Completion gates

The platform is considered complete only when all eight gates below are mechanically checkable:

```text
VERSION_IDENTITY=PASS
NORMATIVE_SPEC=PASS
CONFORMANCE=PASS
DIFFERENTIAL_FUZZ=PASS
SEMANTIC_INVARIANTS=PASS
VERSION_MATRIX=PASS
TOOLING_3X=PASS
REPRODUCIBLE_RELEASE=PASS
```

A ninth aggregate gate may emit:

```text
PLATFORM_COMPLETION=PASS
```

only if the eight constituent gates pass on one exact commit/tree.

## 4. Canonical version identity

### 4.1 Single authority

Introduce `tev_script/version.py` as the source-code authority for the current package/language release identity:

```python
PACKAGE_VERSION = "3.1.0"
CURRENT_LANGUAGE_VERSION = "3.1.0"
CURRENT_PROFILE = "total_core"
```

Historical version modules may continue to expose predecessor identities, but current package/build/CLI descriptors must derive from this authority rather than repeat independent literals.

### 4.2 Build metadata

The repository-root `pyproject.toml` must stop claiming package `1.0.0` and V1-only product identity. It becomes the current development/install surface for 3.1.x, while `packaging/v3` and `packaging/v31` remain preserved certification fixtures for their historical release gates.

A version identity validator checks the current source authority against:

- repository-root `pyproject.toml`;
- current descriptor;
- `release_metadata_v31`;
- current CLI version output;
- current 3.1 schemas/spec discriminators;
- package `__version__` where public;
- `CHANGELOG` current stable entry.

It must distinguish current-authority files from immutable historical fixtures so that predecessor evidence is not rewritten.

## 5. Normative 3.1 platform specification

Add `spec/TEV_SCRIPT_3_1_PLATFORM.md` as an integrating normative document. It does not duplicate all lower specifications; it names the exact normative authorities for:

- lexical/source profiles;
- static semantics;
- modules/linking;
- values and exact arithmetic;
- generics/protocols/collections;
- recursion and bounded execution;
- tasks/async representation;
- effects/capabilities;
- Program IR V4/V5 Total-Core;
- canonical serialization and hashing;
- runtime/checkpoint/continuation behavior;
- error/fail-closed behavior;
- cross-runtime conformance;
- version compatibility and upgrade rules.

Add `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json` containing stable paths plus SHA-256 digests calculated by the completion tooling. The index is the machine-readable normative manifest used by certification.

The completion gate must reject missing normative files, duplicate authority declarations, or stale digests.

## 6. Version and compatibility matrix

Add `spec/TEV_SCRIPT_VERSION_MATRIX.json` and `spec/TEV_SCRIPT_VERSIONING.md`.

The matrix explicitly separates independent version domains:

```text
language
source_profile
linked_program
program_ir
runtime_abi
checkpoint
package
```

Each row declares status (`current`, `compatible`, `historical`), accepted input versions/profiles, output version/profile, semantic authority and migration/lowering route where applicable.

No tool may infer semantic compatibility from numeric similarity alone.

## 7. Tooling 3.x closure

The generic `tev-script` command remains the current entry point. Version-specific commands remain compatibility entry points.

Required generic current commands:

```text
tev-script --version
tev-script describe
tev-script check <source/project>
tev-script compile <source/project>
tev-script run <IR/artifact>
tev-script conformance
tev-script platform-check
```

The existing V1 LSP remains a preserved V1 service. This intervention adds a version-aware LSP/tooling dispatcher rather than deleting it. The dispatcher must reject unsupported 3.1 constructs explicitly instead of silently validating them with V1 semantics.

Formatting is not added unless a canonical formatter can be specified without semantic ambiguity; YAGNI applies.

## 8. Normative conformance corpus

Extend `conformance/` with a 3.1 manifest that binds each case to:

```text
case_id
language/profile
source or IR input hash
expected validation result
expected result/receipt hash where deterministic
required runtimes
```

The initial 3.1 corpus includes:

- Total-Core pure execution;
- bounded recursion;
- collections/generics/protocols;
- task/continuation behavior;
- explicit observations/effect commands;
- capability denial;
- budget exhaustion;
- malformed IR/schema rejection;
- proof-admission rejection/acceptance boundaries;
- checkpoint/replay identity;
- Python/JavaScript parity.

Conformance runners must compare canonical bytes/hashes rather than host-native object formatting.

## 9. Deterministic property and differential fuzzing

Add a stdlib-only deterministic generator; no new runtime dependency is required.

The generator is seed-driven and creates bounded valid/invalid IR/source fragments. Every fuzz receipt records:

```text
seed
case_count
generator_version
runtime identities
first divergence if any
aggregate corpus hash
```

Required properties include:

1. canonicalization idempotence;
2. validate(serialize(parse/construct)) stability where defined;
3. Python/JavaScript result/receipt parity for the generated portable subset;
4. deterministic replay from the same checkpoint;
5. mutation of a bound hash causes fail-closed rejection;
6. observed capabilities are a subset of authorized capabilities;
7. evaluation never exceeds declared finite budgets without a deterministic budget failure.

The harness is deterministic and replayable from one seed; random entropy is never certification authority.

## 10. Constitutional semantic invariant gate

Add a compact gate that composes existing tests/validators instead of reimplementing semantics.

The gate checks witnesses for:

```text
DETERMINISM
CAPABILITY_NON_ESCALATION
BOUNDED_EXECUTION
CANONICAL_IDENTITY
CHECKPOINT_REPLAY_EQUIVALENCE
CROSS_RUNTIME_EQUIVALENCE
UPGRADE_NO_FORK
```

Each witness has an explicit supporting test/gate path. Absence of evidence is HOLD/FAIL, never inferred PASS.

## 11. Reproducible-release and provenance contract

Add a platform release manifest schema and tooling that can compare two independently produced wheel/build artifacts by SHA-256 without performing network publication.

The receipt records:

```text
source_commit
source_tree
normative_index_hash
version_identity_hash
conformance_hash
wheel_sha256
build_environment_descriptor_hash
sbom_sha256
provenance_sha256
```

A deterministic dependency/file SBOM is generated from the package contents and declared build/runtime dependency surfaces. The repository remains zero-runtime-dependency where the current package guarantees that property.

This phase does not publish a new release. It only makes the next release reproducibly certifiable.

## 12. Implementation boundaries

New implementation should be isolated into small modules:

```text
tev_script/version.py
tev_script/platform_versioning.py
tev_script/platform_conformance.py
tev_script/platform_fuzz.py
tev_script/platform_completion.py

tools/validate_platform_version_identity.py
tools/run_platform_conformance.py
tools/run_platform_differential_fuzz.py
tools/validate_platform_completion.py
```

Existing semantic/runtime modules are modified only where needed to expose stable current-version metadata or a generic dispatcher. No broad refactor of `source_program_v2.py`, IR engines or runtime semantics is authorized by this closure.

## 13. Testing strategy

Implementation follows test-first changes. Tests are split by concern:

```text
tests/test_platform_version_identity.py
tests/test_platform_normative_spec.py
tests/test_platform_version_matrix.py
tests/test_platform_tooling.py
tests/test_platform_conformance_v31.py
tests/test_platform_differential_fuzz.py
tests/test_platform_invariants.py
tests/test_platform_reproducible_release.py
tests/test_platform_completion.py
```

Every completion gate has at least one negative counterexample. Certification tests must prove that stale version metadata, stale normative hashes, a runtime divergence, an unauthorized capability, an over-budget run, or a mismatched artifact prevents aggregate completion.

## 14. Acceptance criteria

The branch is ready for review when:

1. all eight completion gates emit PASS on the exact branch HEAD/tree;
2. predecessor v3.1.0 identity remains unchanged;
3. current package/source metadata no longer claims V1/1.0.0 as current;
4. the normative 3.1 index is internally consistent and content-addressed;
5. the version matrix resolves every current public CLI/runtime path;
6. deterministic differential fuzzing completes with no Python/JavaScript divergence on its certified bounded corpus;
7. all added negative tests fail closed as intended;
8. existing focal/full tests relevant to touched surfaces pass;
9. repository changes remain confined to platform closure scope;
10. no merge, release, tag or stable promotion is performed.
