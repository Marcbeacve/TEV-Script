# TEVScript 3.1 Platform Completion

Status: implementation candidate. Full-repository certification is required before merge or any new release claim.

## Purpose

TEVScript MAX 3.1.0 already closes the Total-Core semantic basis. Platform completion closes the engineering authority around that basis without making the runtime more permissive and without reinterpreting historical V1/V2/V3 semantics.

The completion relation is:

```text
published 3.1 Total-Core semantic core
+ canonical current version identity
+ normative platform specification
+ explicit version-domain compatibility
+ version-aware tooling boundaries
+ executable conformance campaign
+ deterministic differential fuzzing
+ constitutional invariant witnesses
+ reproducible artifact/SBOM/provenance evidence
= platform completion candidate
```

## Current-version authority

`tev_script/version.py` is the single current source-code identity:

```text
PACKAGE_VERSION=3.1.0
CURRENT_LANGUAGE_VERSION=3.1.0
CURRENT_PROFILE=total_core
```

`platform_versioning.py` cross-checks this authority against root package metadata, the dedicated V31 packaging authority and V31 release metadata. Historical packaging fixtures remain explicitly historical and are not rewritten to fake current identity.

## Normative specification

`spec/TEV_SCRIPT_3_1_PLATFORM.md` integrates the existing source/static-semantics, value, IR, capability, checkpoint and update authorities. `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json` freezes the exact authority files by Git blob identity; local validation additionally emits SHA-256 per file and an aggregate normative-set SHA-256.

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

A route is compatible only when an exact matrix row authorizes it. Numeric equality never implies compatibility.

## Tooling boundary

The generic `tev-script` command reports current platform identity and can run the foundational platform check. Historical generic compiler commands remain compatibility behavior instead of being silently reinterpreted as Total-Core. Current Total-Core compile/run authority remains `tev-script-v31`.

The generic `tev-script-lsp` is version-aware. It may delegate to the V1 LSP only when `--language-version 1.0.0` is explicit. For current 3.1 source it returns HOLD until a genuine 3.1 LSP exists. Silent V1 fallback is forbidden.

## Executable conformance

`conformance/v31-platform-manifest.json` binds exact test identities for:

- Program IR V5 Total-Core;
- Total-Core runtime;
- 3.1 source compilation;
- Python/independent-JavaScript byte parity;
- bounded step limits;
- checkpoint/replay;
- V31 authority boundaries.

`platform_conformance.py` verifies each test file identity before execution. Required missing runtimes produce HOLD, never PASS.

## Differential fuzzing

`platform_fuzz.py` generates deterministic bounded Total-Core programs from an explicit seed. The initial generated family explores finite `jump`/`halt` control-flow graphs under finite quantum limits and up to three continuation epochs.

For each case the certification runner compares Python and the independent JavaScript Total-Core runtime on canonical result bytes. It also mutates `program_hash` and requires both implementations to reject the tampered program.

A divergence receipt contains the first failing case and source so the campaign can be replayed exactly.

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

Witness targets are themselves bound by exact Git blob identity. Missing evidence is HOLD/FAIL.

## Reproducible release evidence

`platform_release.py` performs two isolated wheel builds with deterministic build variables and requires byte-identical SHA-256 results. It also constructs a deterministic package-file/dependency SBOM and provenance binding:

```text
source commit
source tree
wheel SHA-256
SBOM SHA-256
normative-set SHA-256
version-identity SHA-256
provenance SHA-256
```

No timestamp participates in canonical provenance identity.

## Aggregate authority

Run from a complete clean checkout:

```powershell
python RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py --receipt TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT.json
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

## Development verification performed during implementation

The implementation environment could not materialize the full GitHub checkout because outbound DNS/download access is unavailable. A local synthetic-root TDD harness was therefore used to exercise the new platform modules independently.

Result:

```text
41 passed
```

The campaign includes positive and negative tests for the platform layer. It is not a substitute for the full repository regression or the aggregate completion gate on a complete checkout.
