# TEVScript 3.1 — Complete Documentation System Implementation Plan

> **For agentic workers:** implement task-by-task with TDD for every tooling, behavior or bug-fix change. No production-code correction is written before an observed failing test. Documentation-only pages remain subordinate to normative language authority.

**Goal:** Build a complete Spanish TEVScript 3.1 documentation system with executable examples, exhaustive current-surface coverage, structured diagnostic reference, deterministic offline validation and correction of contradictions discovered during the audit.

**Design authority:** `docs/superpowers/specs/2026-08-18-tevscript-documentation-system-design.md`

**Base:** `main@a0c3951a03403f871ff4a192f75f2c29437f5fdb`

**Working branch:** `agent/tevscript-docs-python-style-v1`

**Current identities:** package candidate `3.1.2`; language `3.1.0`; profile `total_core`; immediate published package predecessor `3.1.1`; archived V31 package authority `3.1.0`.

**Tech stack:** Python 3.11+ stdlib, pytest/unittest already present in the repository, existing TEVScript compiler/runtime APIs, Markdown, JSON, canonical repository paths. Documentation validation is deterministic and network-free. No new runtime dependency. No GitHub Actions.

## Global constraints

- Work only on `agent/tevscript-docs-python-style-v1`.
- Do not merge, tag, publish or promote stable state.
- Normative specifications, schemas, IR/value models, ABI and conformance remain semantic authority.
- Python/JavaScript/C#/Unity are implementation witnesses, never language authority.
- Do not redesign syntax or add semantic primitives inside this project.
- Preserve historical documentation/evidence; classify it rather than deleting it.
- Every executable Markdown example is bound to a canonical file through `<!-- tevdoc-source: ... -->`.
- Negative examples bind the expected diagnostic with `<!-- tevdoc-expect-diagnostic: CODE -->` and `case.json`.
- Long repository-wide certification runs only at coherent checkpoints; focused RED/GREEN tests run immediately.

---

## Phase A — foundation and truth audit

### Task A1 — RED: separate immediate package predecessor from archived V31 package identity

**Files:**
- Modify test first: `tests/test_platform_version_identity.py`
- Then modify: `tev_script/version.py`
- Then modify: `tev_script/platform_versioning.py`
- Then modify: `spec/TEV_SCRIPT_3_1_PLATFORM.md`
- Then update content binding: `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json`
- Existing evidence: `CHANGELOG.md`, `README.md`, `docs/STATUS.md`, `spec/TEV_SCRIPT_VERSION_MATRIX.json`

**Root-cause hypothesis to prove:** one variable, `PUBLISHED_PREDECESSOR_PACKAGE_VERSION`, is currently being used for two different version domains: the immediate published predecessor of package `3.1.2` and the archived V31 package artifact at `packaging/v31/pyproject.toml`. Those identities are now `3.1.1` and `3.1.0` respectively and must be represented independently.

- [ ] Change `tests/test_platform_version_identity.py` so the intended contract is explicit:
  - `PUBLISHED_PREDECESSOR_PACKAGE_VERSION == "3.1.1"`;
  - add `ARCHIVED_V31_PACKAGE_VERSION == "3.1.0"`;
  - repository receipt reports both identities independently;
  - `packaging/v31/pyproject.toml` is checked against the archived V31 identity, not the immediate predecessor;
  - platform spec reports immediate predecessor `3.1.1`.
- [ ] Run `python -m pytest -q tests/test_platform_version_identity.py` and require RED on the predecessor distinction, not on import/syntax mistakes.
- [ ] Implement only the split in `tev_script/version.py` and `tev_script/platform_versioning.py`.
- [ ] Correct the contradictory normative assignment in `spec/TEV_SCRIPT_3_1_PLATFORM.md` to `published_predecessor_package = 3.1.1`; preserve explicit archived V31 `3.1.0` prose.
- [ ] Recompute only the Git blob SHA-1 entry for `spec/TEV_SCRIPT_3_1_PLATFORM.md` in `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json`.
- [ ] Run `python -m pytest -q tests/test_platform_version_identity.py tests/test_platform_normative_spec.py tests/test_platform_version_matrix.py tests/test_platform_tooling.py` and require GREEN.
- [ ] Run `python -m tev_script.cli platform-check --root .` and require all four foundational gates PASS.
- [ ] Commit one focused version-governance correction.

### Task A2 — RED: documentation validator receipt contract

**Files:**
- Create test first: `tests/test_documentation_v31.py`
- Then create: `tools/validate_documentation_v31.py`

**Interface:**
- `validate_documentation(root: Path) -> dict[str, object]`
- CLI emits canonical JSON-like deterministic JSON and exits `0` on PASS, `1` on FAIL.
- Receipt schema: `TEV_SCRIPT_DOCUMENTATION_VALIDATION_RECEIPT_V1`.

Initial check families are fixed:

```text
VERSION_IDENTITY
MANUAL_ROOT
COVERAGE_MANIFEST
INTERNAL_PATHS
SOURCE_BINDINGS
EXAMPLE_CASES
DIAGNOSTIC_COVERAGE
PUBLIC_SURFACE_COVERAGE
HISTORICAL_CLASSIFICATION
```

- [ ] RED test: absent `docs/manual/` produces deterministic FAIL with `MANUAL_ROOT` failure.
- [ ] RED test: receipt field/check ordering is deterministic.
- [ ] Implement minimal validator skeleton; do not create empty PASS placeholders for unimplemented checks. Unimplemented required checks fail closed.
- [ ] GREEN focused tests.
- [ ] Commit.

### Task A3 — RED: exact Markdown source-binding parser

**Files:**
- Extend first: `tests/test_documentation_v31.py`
- Then extend: `tools/validate_documentation_v31.py`

- [ ] RED cases: missing source, fence drift, duplicate directive, wrong fence association, negative directive without matching case expectation.
- [ ] Implement exact `tevdoc-source` binding with only CRLF/LF normalization and optional one terminal newline removal.
- [ ] Implement `tevdoc-expect-diagnostic` association.
- [ ] GREEN tests.
- [ ] Commit.

### Task A4 — RED: example `case.json` execution contract

**Files:**
- Extend first: `tests/test_documentation_v31.py`
- Then extend: `tools/validate_documentation_v31.py`
- Create first fixture cases under `examples/docs/v31/getting_started/` and `examples/docs/v31/diagnostics/`.

Supported operations in V1 documentation cases are exactly:

```text
check
compile
run
expect_failure
```

- [ ] RED malformed/unknown operation tests.
- [ ] RED positive compile/check fixture.
- [ ] RED negative fixture asserting one exact `TevScriptError.diagnostic.code`.
- [ ] Implement bounded case loading/execution through current TEVScript APIs/CLI semantics, not a second interpreter.
- [ ] GREEN tests.
- [ ] Commit.

### Task A5 — RED: coverage manifest schema and closure

**Files:**
- Extend first: `tests/test_documentation_v31.py`
- Create: `docs/manual/DOCUMENTATION_COVERAGE_V1.json`
- Extend: `tools/validate_documentation_v31.py`

Coverage domains are exactly:

```text
language_constructs
cli_surface
python_api
source_profiles
ir_runtime_profiles
diagnostics
integrations
version_domains
```

- [ ] RED missing-domain and duplicate-id tests.
- [ ] RED entry pointing to missing page/evidence test.
- [ ] Implement parser/validator with deterministic ordering and fail-closed unknown fields.
- [ ] Start manifest only with surfaces whose pages are created in Phase A; required-but-not-yet-documented current surfaces remain explicit uncovered failures until their phase closes.
- [ ] GREEN synthetic validator tests; repository-level documentation receipt may legitimately remain FAIL until coverage is complete.
- [ ] Commit.

### Task A6 — current manual front door and version truth pages

**Files:**
- Create: `docs/manual/README.md`
- Create: `docs/manual/documentation-policy.md`
- Create: `docs/manual/versions/current.md`
- Create: `docs/manual/versions/version-domains.md`
- Create: `docs/manual/versions/compatibility.md`
- Create: `docs/manual/glossary.md`
- Modify: `README.md` only to point current readers to `docs/manual/README.md`; preserve historical body.
- Extend tests: `tests/test_documentation_v31.py`

- [ ] Add tests that current pages bind package `3.1.2`, language `3.1.0`, profile `total_core`, immediate predecessor `3.1.1`, archived V31 `3.1.0`.
- [ ] Add tests that current landing links to Tutorial, Language Reference, API, CLI, HOWTO, diagnostics, integrations, internals and versions destinations.
- [ ] Write the Spanish pages with no placeholder/TODO text.
- [ ] Update coverage entries for version domains and manual root.
- [ ] Run documentation tests plus version/platform focused tests.
- [ ] Commit Phase-A documentation foundation.

### Task A7 — diagnostic and public-surface inventory generators/checkers

**Files:**
- Extend first: `tests/test_documentation_v31.py`
- Extend: `tools/validate_documentation_v31.py`
- Read-only inventory sources: `tev_script/__init__.py`, `tev_script/cli.py`, `tev_script/source_total_core_v31.py`, current matrix/entrypoints.

- [ ] RED test: adding a synthetic public `__all__` symbol without coverage makes `PUBLIC_SURFACE_COVERAGE` fail.
- [ ] RED test: adding a synthetic `TEVS_V31_*` structured user diagnostic without coverage makes `DIAGNOSTIC_COVERAGE` fail.
- [ ] Implement AST/static inventory; do not import arbitrary host code merely to discover symbols.
- [ ] Classify Python exports as `PUBLIC_SUPPORTED`, `PUBLIC_COMPATIBILITY`, `INTERNAL`, or `DEPRECATED` via manifest data; no guessed publicness.
- [ ] Produce deterministic missing/extra lists.
- [ ] Commit.

### Phase-A checkpoint

Run:

```text
python -m pytest -q tests/test_platform_version_identity.py tests/test_platform_normative_spec.py tests/test_platform_version_matrix.py tests/test_platform_tooling.py tests/test_documentation_v31.py
python -m tev_script.cli platform-check --root .
python tools/validate_documentation_v31.py --root .
```

Expected at the end of Phase A:
- version/platform focused tests PASS;
- documentation validator infrastructure PASS for implemented checks;
- aggregate documentation status may remain FAIL only for explicitly reported surface coverage assigned to later phases; no hidden/placeholder PASS is allowed.

---

## Phase B — Getting Started and current CLI reference

### Task B1 — executable first Total-Core program

**Files:**
- `docs/manual/getting-started/installation.md`
- `docs/manual/getting-started/first-program.md`
- `docs/manual/getting-started/cli-workflow.md`
- `docs/manual/getting-started/project-layout.md`
- `docs/manual/getting-started/editor-lsp.md`
- `docs/manual/getting-started/mental-model.md`
- canonical cases under `examples/docs/v31/getting_started/`

- [ ] Add/observe RED source-binding/example tests before writing each executable example.
- [ ] Cover install → check → compile → run, project/unit mapping, LSP and mental model.
- [ ] Update coverage manifest; require no undocumented Getting Started command used by examples.

### Task B2 — exhaustive generic CLI reference

**Files:**
- Create pages under `docs/manual/cli-reference/` for `--version`, `describe`, `descriptor`, `check`, `compile`, `run`, `conformance`, `platform-check`.
- Canonical cases under `examples/docs/v31/cli/`.

- [ ] Inventory `tev_script.cli.build_parser()` statically.
- [ ] RED when a current command/option lacks a coverage entry.
- [ ] Document synopsis, args/options, input artifact, output schema, exit code, positive/negative example, version/profile.
- [ ] Close `cli_surface` coverage.

---

## Phase C — progressive tutorial

Create the 15 approved tutorial chapters under `docs/manual/tutorial/` and canonical examples under `examples/docs/v31/tutorial/` in dependency order:

```text
01 values/exactness
02 names/bindings/expressions
03 control/bounds
04 functions/types
05 data models
06 state/events
07 capabilities/effects
08 modules/composition
09 Field/Transformation/Apply
10 processes/continuations
11 V4 units
12 Total-Core
13 proof admissions
14 checkpoints/replay
15 complete application
```

For each chapter:
- [ ] RED binding/case test first.
- [ ] Write complete Spanish explanation and executable source.
- [ ] Validate positive/negative behavior.
- [ ] Link every semantic claim to the corresponding reference/spec path.
- [ ] Update coverage only after the page and evidence exist.

---

## Phase D — current language reference

**Files:** pages under `docs/manual/language-reference/`, examples under `examples/docs/v31/language/`.

- [ ] Build accepted-source-form inventory from V2 source authority, V3 semantic-process source and V31 Total-Core frontend.
- [ ] For every accepted form classify exactly `CURRENT`, `INHERITED_COMPATIBILITY`, `INTERNAL`, or `REJECTED`.
- [ ] RED when an accepted current form lacks a page/coverage entry.
- [ ] Document lexical structure, comments, identifiers, literals, exact values, types, expressions/operators, declarations, functions, bounds/recursion contracts, effects, state/events, modules, semantic-process declarations, Field/Transformation/Apply, Total-Core units, `invoke_v4`, proof admission and source-to-IR boundary.
- [ ] Close `language_constructs` and `source_profiles` coverage.

---

## Phase E — Python library/API reference

**Files:** pages under `docs/manual/library-reference/`; tests remain in `tests/test_documentation_v31.py` or split to `tests/test_documentation_api_v31.py` if file size warrants.

- [ ] Inventory `tev_script.__all__` and explicit versioned compatibility surfaces.
- [ ] RED on an exported supported symbol missing from coverage.
- [ ] Document qualified name, signature, parameters, return, diagnostics/exceptions, side effects, canonical identity implications, version/profile, example and related symbols.
- [ ] Keep V0.2/V1 compatibility APIs visibly separate from current Total-Core APIs.
- [ ] Close `python_api` coverage.

---

## Phase F — diagnostics reference

**Files:** pages/index under `docs/manual/diagnostics/`; negative cases under `examples/docs/v31/diagnostics/`.

- [ ] Inventory deliberately user-visible structured diagnostics in current frontends/runtime/tooling.
- [ ] RED for every current code absent from coverage.
- [ ] For each code document phase, meaning, trigger, failing example, expected exact code, corrected example and related rule.
- [ ] Execute all negative examples; success where failure is expected is a validator failure.
- [ ] Close `diagnostics` coverage.

---

## Phase G — HOWTO and integrations

Create approved HOWTO pages under `docs/manual/howto/` and integration pages for Python, JavaScript, C#, Unity, Browser-WASM, WASI and filesystem under `docs/manual/integrations/`; canonical examples live under matching `examples/docs/v31/` trees.

- [ ] Every host page distinguishes TEVScript semantics, adapter/provider responsibility, host conversion/approximation, capability grant and unsupported deployment assumptions.
- [ ] RED on supported integration listed in coverage without a page/evidence case.
- [ ] Close `integrations` coverage.

---

## Phase H — internals, historical navigation and closure

**Files:**
- `docs/manual/internals/*`
- `docs/manual/versions/v1.md`, `v2.md`, `v3.md`, `v31.md`, `deprecations.md`
- `docs/manual/faq.md`
- final `docs/manual/glossary.md`
- final `docs/manual/DOCUMENTATION_COVERAGE_V1.json`
- `docs/VALIDATION.md`
- optionally `REPOSITORY_CHANNEL.json` only if governance requires the documentation validator as a changed-path validation command.

- [ ] Document frontend → semantic identity → IR V2/V3/V4/V5 → runtime → checkpoint/proof/capability boundaries.
- [ ] Make historical/current navigation unambiguous without rewriting historical evidence.
- [ ] Require all coverage domains closed with no missing and no nonexistent current surface.
- [ ] Add validator command to `docs/VALIDATION.md`.
- [ ] Integrate the validator only as a documentation-quality leaf; do not alter the nine-gate platform semantic/certification authority unless separately designed.

---

## Final verification

Before claiming completion:

```text
python -m pytest -q tests/test_documentation_v31.py
python -m pytest -q tests/test_platform_version_identity.py tests/test_platform_normative_spec.py tests/test_platform_version_matrix.py tests/test_platform_tooling.py
python tools/validate_documentation_v31.py --root .
python -m tev_script.cli platform-check --root .
```

Then use repository governance to select causally required conformance/full validation. Because this branch will change `tests/**`, `examples/**`, `tools/**` and one normative spec/index during the version correction, final validation must include every rule selected by `REPOSITORY_CHANNEL.json`; documentation work cannot downgrade those requirements.

Final acceptance requires the design Definition of Done, zero undocumented current public surfaces, zero documented nonexistent current surfaces, no placeholder/TODO sections, deterministic executable example results, clean exact Git identity, and `MERGE_AUTHORITY=FALSE` / `PUBLICATION_AUTHORITY=FALSE` until the user explicitly authorizes otherwise.