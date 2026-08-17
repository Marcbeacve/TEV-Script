# TEVScript Platform Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close TEVScript 3.1.x as a coherent, externally implementable and reproducibly certifiable platform without changing the published Total-Core semantics.

**Architecture:** Add a thin fail-closed platform layer around existing semantics. Historical V1/V2/V3 artifacts remain compatibility evidence; current 3.1 identity, normative specification, compatibility, tooling, conformance, deterministic fuzzing, invariant witnesses and reproducible-release evidence compose into one aggregate completion receipt.

**Tech Stack:** Python 3.11+ stdlib, existing TEVScript Python/JavaScript runtimes, Node.js for parity, existing schemas/tests, local certification only.

## Global Constraints

- Preserve `v3.1.0`, commit `c20718ddb2223ba0bfd05ff59006ca31e2966b0b`, tree `812b140c5e6fb7232ef379773d9c37e8f3459f4c` and published wheel bytes.
- No runtime becomes semantic authority; no production runtime interprets `.tevs` source.
- Effects remain explicit capabilities; arithmetic remains exact until explicit host conversion.
- Missing authority, budget, schema or identity fails closed.
- No new runtime dependencies, no GitHub Actions, no merge/release/tag/stable promotion.

---

### Task 1: Canonical version identity

**Files:** create `tev_script/version.py`, `tev_script/platform_versioning.py`, `tools/validate_platform_version_identity.py`, `tests/test_platform_version_identity.py`; modify root `pyproject.toml`, `tev_script/__init__.py`, `tev_script/cli.py`.

**Produces:** `PACKAGE_VERSION`, `CURRENT_LANGUAGE_VERSION`, `CURRENT_PROFILE`, `validate_current_version_identity(root)`.

- [ ] Write tests asserting current package/language `3.1.0` and `status == PASS`.
- [ ] Run `python -m pytest tests/test_platform_version_identity.py -q` and observe failure.
- [ ] Implement single current-version authority; update root metadata only, preserving historical packaging fixtures.
- [ ] Run identity plus V31 packaging/descriptor tests; commit `fix(platform): unify current TEVScript version identity`.

### Task 2: Normative 3.1 specification

**Files:** create `spec/TEV_SCRIPT_3_1_PLATFORM.md`, `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json`, `tev_script/platform_spec.py`, `tests/test_platform_normative_spec.py`.

**Produces:** `build_normative_index(root)`, `validate_normative_index(root)`.

- [ ] Write failing tests for missing/stale normative digests.
- [ ] Implement integrating spec and sorted SHA-256 index over exact authority files.
- [ ] Validate that duplicate/missing/stale entries fail closed; commit `docs(platform): bind normative TEVScript 3.1 specification`.

### Task 3: Explicit version matrix

**Files:** create `spec/TEV_SCRIPT_VERSIONING.md`, `spec/TEV_SCRIPT_VERSION_MATRIX.json`, `tev_script/platform_compatibility.py`, `tests/test_platform_version_matrix.py`.

**Produces:** `validate_version_matrix(root)`, `resolve_runtime_route(domain, version, profile=None)`.

- [ ] Write failing tests requiring separate language/source/IR/runtime/checkpoint/package domains.
- [ ] Implement explicit current/compatible/historical rows and reject compatibility inferred from numeric equality alone.
- [ ] Run matrix and V31 authority tests; commit `feat(platform): make version compatibility explicit`.

### Task 4: Version-aware tooling

**Files:** create `tev_script/platform_tooling.py`, `tev_script/lsp.py`, `tests/test_platform_tooling.py`; modify `tev_script/cli.py`, root `pyproject.toml`.

**Produces:** current `--version`, `describe`, `platform-check`, and a version-aware LSP dispatcher preserving `lsp_v1`.

- [ ] Write failing CLI/tooling tests.
- [ ] Implement generic dispatch through the compatibility matrix without duplicating compilers.
- [ ] Ensure unsupported current constructs never fall back silently to V1 semantics.
- [ ] Run tooling/V1-LSP/V31-CLI tests; commit `feat(tooling): add version-aware TEVScript 3.x dispatch`.

### Task 5: Normative 3.1 conformance

**Files:** create `conformance/v31-platform-manifest.json`, `tev_script/platform_conformance.py`, `tools/run_platform_conformance.py`, `tests/test_platform_conformance_v31.py`.

**Produces:** `run_platform_conformance(root, node_executable="node")`.

- [ ] Write failing PASS/negative-boundary tests.
- [ ] Bind existing Total-Core, bounded recursion, collections/generics, effect/capability, budget, proof, checkpoint and Python/JS parity fixtures by hashes.
- [ ] Compare canonical bytes/hashes; unavailable required runtime yields HOLD, never PASS.
- [ ] Run focal parity/runtime tests; commit `test(platform): add normative 3.1 conformance gate`.

### Task 6: Deterministic differential/property fuzzing

**Files:** create `tev_script/platform_fuzz.py`, `tools/run_platform_differential_fuzz.py`, `tests/test_platform_differential_fuzz.py`.

**Produces:** `generate_cases(seed, count)`, `run_differential_fuzz(root, seed, count, node_executable="node")`.

- [ ] Write tests proving seed replayability and mutated hashes/budget violations fail closed.
- [ ] Implement stdlib-only bounded generator using `random.Random(seed)` and existing constructors.
- [ ] Compare Python/JS canonical results on the generated portable subset and record first divergence.
- [ ] Run fuzz/parity tests; commit `test(platform): add deterministic differential fuzzing`.

### Task 7: Constitutional invariant witnesses

**Files:** create `tev_script/platform_invariants.py`, `tests/test_platform_invariants.py`.

**Produces:** `validate_platform_invariants(root)` with exactly `DETERMINISM`, `CAPABILITY_NON_ESCALATION`, `BOUNDED_EXECUTION`, `CANONICAL_IDENTITY`, `CHECKPOINT_REPLAY_EQUIVALENCE`, `CROSS_RUNTIME_EQUIVALENCE`, `UPGRADE_NO_FORK`.

- [ ] Write failing witness/negative missing-evidence tests.
- [ ] Compose exact existing gates/tests rather than copying semantics.
- [ ] Missing witness is HOLD/FAIL; run focal invariant tests and commit `test(platform): certify constitutional semantic invariants`.

### Task 8: Reproducible release evidence

**Files:** create `schemas/tev-script-platform-release-receipt-v1.schema.json`, `tev_script/platform_release.py`, `tools/build_platform_release_evidence.py`, `tests/test_platform_reproducible_release.py`.

**Produces:** deterministic `build_sbom(root)`, provenance builder, artifact SHA-256 comparison and release-evidence validator.

- [ ] Write deterministic SBOM and equal/different artifact tests.
- [ ] Implement sorted package/dependency SBOM and provenance binding commit/tree, normative-index hash and version-identity hash; timestamps cannot affect canonical identity.
- [ ] Run V31 packaging tests and commit `feat(platform): add reproducible release provenance gate`.

### Task 9: Aggregate completion gate

**Files:** create `tev_script/platform_completion.py`, `tools/validate_platform_completion.py`, `RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py`, `tests/test_platform_completion.py`.

**Produces:** `validate_platform_completion(root, fuzz_seed=31031, fuzz_count=128)`.

- [ ] Write failing test requiring all eight gates and a negative injected FAIL.
- [ ] Compose public platform validators; HOLD never upgrades to PASS.
- [ ] Emit the eight named `=PASS` fields and `PLATFORM_COMPLETION=PASS` only on total success.
- [ ] Run all `tests/test_platform_*.py`; commit `feat(platform): close aggregate TEVScript completion gate`.

### Task 10: Documentation and regression closure

**Files:** modify `README.md`, `PROJECT_STATE.md`, `docs/STATUS.md`, `CHANGELOG.md`; create `docs/TEV_SCRIPT_3_1_PLATFORM_COMPLETION.md`.

- [ ] Make root docs current for stable 3.1.0 while clearly marking this branch as an unmerged platform-completion candidate.
- [ ] Run V31 focal tests, all platform tests, then `python -m pytest -q`.
- [ ] Run `python RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py`; require all eight gates plus aggregate PASS.
- [ ] Verify clean/scoped diff; prepare draft PR only. Commit `docs(platform): close TEVScript 3.1 platform completion candidate`.
