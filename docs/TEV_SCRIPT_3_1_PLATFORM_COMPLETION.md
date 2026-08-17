# TEVScript 3.1 Platform Completion

Status: implementation candidate. Full-repository certification is required before merge or any new release claim.

## Purpose

TEVScript MAX 3.1.0 already closes the Total-Core semantic basis. Package `3.1.1` is the platform/tooling completion candidate over the unchanged language semantics `3.1.0`. It closes engineering authority around that basis without making the runtime more permissive and without reinterpreting historical V1/V2/V3 semantics.

The completion relation is:

```text
published 3.1.0 Total-Core semantic core
+ canonical current version identity
+ normative platform specification
+ explicit version-domain compatibility
+ current generic CLI/LSP
+ executable semantic-area conformance
+ deterministic Total-Core differential fuzzing
+ Total-Core constitutional invariant witnesses
+ clean-source reproducible artifact/SBOM/provenance evidence
= platform completion candidate 3.1.1
```

## Current-version authority

`tev_script/version.py` is the single current source-code identity:

```text
PACKAGE_VERSION=3.1.1
CURRENT_LANGUAGE_VERSION=3.1.0
CURRENT_PROFILE=total_core
PUBLISHED_PREDECESSOR_PACKAGE_VERSION=3.1.0
```

Package version and language version are independent domains. `platform_versioning.py` cross-checks root package metadata, the immutable published V31 packaging authority, V31 release metadata, the V31 descriptor, platform spec, version matrix, public `__version__`, generic CLI version binding and changelog predecessor identities.

Historical packaging/release evidence remains immutable and is never rewritten to fake current identity.

## Normative specification

`spec/TEV_SCRIPT_3_1_PLATFORM.md` integrates the existing source/static-semantics, value, IR, capability, checkpoint and update authorities. `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json` freezes the exact authority files by Git blob identity; validation recomputes those identities and emits SHA-256 per file plus an aggregate normative-set SHA-256.

Runtime implementations never become semantic authority.

## Version domains

`spec/TEV_SCRIPT_VERSION_MATRIX.json` separates:

```text
language
source_profile
linked_program
program_ir
runtime_abi
checkpoint
package
```

`platform_compatibility.py` requires every authority path to exist, every declared entrypoint to resolve, exactly one current row for current domains, exact current package/language identity and the `total_core` profile for the current source/IR/runtime/checkpoint routes. Numeric equality never implies compatibility.

## Current tooling boundary

The generic command is now the current platform entry point:

```text
tev-script --version
tev-script describe
tev-script descriptor
tev-script check
tev-script compile
tev-script run
tev-script conformance
tev-script platform-check
```

`check`, `compile` and `run` delegate to the same Total-Core 3.1 implementation used by `tev-script-v31`; no second compiler/runtime is introduced. Historical CLIs remain available only through their explicit versioned entry points.

The generic `tev-script-lsp` dispatches current language `3.1.0` to `lsp_v31.py`. That server validates source through `compile_total_core_v31` and supports standalone process source plus explicit project bindings (`--process`, `--unit`, `--effect-input`, `--proof-admission`). V1 LSP remains available only when `--language-version 1.0.0` is explicit. Unknown versions fail closed.

## Executable conformance

`conformance/v31-platform-manifest.json` is schema V2 and requires explicit coverage of all current semantic areas:

```text
total_core_ir
total_core_runtime
total_core_source
collections_generics_protocols
tasks_continuations
effects_capabilities
budget_exhaustion
malformed_ir_rejection
proof_admission_boundary
checkpoint_replay
cross_runtime_parity
```

Each case binds an exact test-file Git blob identity and declares `expected_status=PASS`. Missing semantic areas fail the campaign before execution. Missing required runtimes produce HOLD, never PASS. The receipt binds the manifest SHA-256 and each executed target SHA-256.

## Differential fuzzing

`platform_fuzz.py` generates deterministic bounded Total-Core campaigns from an explicit seed. Required case families are:

```text
control_flow
branch_apply
invoke_pure
invoke_recursive
invoke_effects
proof_apply
```

A campaign that does not contain every required family is HOLD rather than PASS. External unit/effect/proof inputs are part of the content-addressed corpus identity.

For each case, Python and the independent JavaScript Total-Core runtime must produce identical canonical result bytes epoch by epoch. Program-hash tampering must be rejected by both implementations. The first divergence is emitted with the replayable case/source.

## Constitutional invariants

`platform_invariants.py` requires executable witnesses for exactly:

```text
DETERMINISM
CAPABILITY_NON_ESCALATION
BOUNDED_EXECUTION
CANONICAL_IDENTITY
CHECKPOINT_REPLAY_EQUIVALENCE
CROSS_RUNTIME_EQUIVALENCE
UPGRADE_NO_FORK
```

The first five are now direct Total-Core V5 witnesses. Cross-runtime equivalence is witnessed by the independent JavaScript V5 parity suite. Governed update/no-fork retains its independently certified update witness. Witness targets are themselves content-addressed; missing tools are HOLD and identity mismatch is FAIL.

## Reproducible release evidence

`platform_release.py` refuses release evidence unless the Git worktree is clean, current version identity passes, the normative set passes and platform conformance is PASS. It then performs two isolated wheel builds with deterministic build variables and requires byte-identical SHA-256 results.

The release receipt V2 binds:

```text
source commit
source tree
wheel SHA-256
SBOM SHA-256
normative-set SHA-256
version-identity SHA-256
conformance receipt SHA-256
build-environment descriptor SHA-256
provenance SHA-256
runtime dependency count = 0
```

No timestamp participates in canonical provenance identity. Schema V1 remains preserved historically; V2 has its own schema file.

## Aggregate authority

Run from a complete clean checkout with Python and Node available:

```powershell
python .\RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py --receipt TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT.json
```

The runner executes all eight gates and prints:

```text
CONFORMANCE=<PASS|HOLD|FAIL>
DIFFERENTIAL_FUZZ=<PASS|HOLD|FAIL>
NORMATIVE_SPEC=<PASS|HOLD|FAIL>
REPRODUCIBLE_RELEASE=<PASS|HOLD|FAIL>
SEMANTIC_INVARIANTS=<PASS|HOLD|FAIL>
TOOLING_3X=<PASS|HOLD|FAIL>
VERSION_IDENTITY=<PASS|HOLD|FAIL>
VERSION_MATRIX=<PASS|HOLD|FAIL>
PLATFORM_COMPLETION=<PASS|HOLD|FAIL>
```

A single FAIL makes the aggregate FAIL. If no gate fails but one or more are HOLD, the aggregate is HOLD. Only eight simultaneous PASS values authorize `PLATFORM_COMPLETION=PASS`.

This gate grants no merge, release, tag or stable-promotion authority.

## Verification status in this implementation environment

The connector/container used for implementation cannot materialize the complete GitHub checkout through its local network path. Focused/synthetic TDD was used while building the isolated platform organs, and several false-PASS conditions were found and removed (unsupported current LSP, unresolved version authorities, inherited-only invariant claims, incomplete fuzz families, incomplete conformance coverage and dirty-source release evidence).

Those focused checks are development evidence only. They are not promoted to full-repository certification. The authoritative result remains pending execution of `RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py` from a complete clean checkout.
