# TEVScript 3.1 Platform — Normative Integration

Status: normative integration profile for the TEVScript 3.1 platform-completion candidate.

This document does not replace predecessor language, IR, value-model or runtime specifications. It defines their authority ordering and the exact composition that constitutes the TEVScript 3.1 platform.

## 1. Current identity

```text
package_version = 3.1.2
language_version = 3.1.0
current_profile = total_core
published_predecessor_package = 3.1.1
```

The current source-code identities are defined in `tev_script/version.py`. Package version and language version are independent domains: package `3.1.2` is the post-publication dogfood/static-closure correction candidate over unchanged Total-Core language semantics `3.1.0`. Package/tag `3.1.1` is the immutable immediate package predecessor and MUST NOT be rebuilt with different bytes under the same version. The archived `3.1.0` V31 packaging authority remains immutable predecessor evidence. Historical V1/V2/V3 identities remain valid only for their explicitly versioned compatibility surfaces.

## 2. Authority rule

Semantic authority belongs to specification, grammar/static-semantics contracts, canonical schemas, IR/value models, ABI/checkpoint contracts and conformance receipts. Python, JavaScript, C#, Unity and future runtimes are implementations and witnesses, not semantic authorities.

If two implementation behaviors disagree, neither implementation may redefine the language. The disagreement is a conformance failure until resolved against the normative authority set.

## 3. Normative authority set

The machine-readable authority set is `spec/TEV_SCRIPT_3_1_NORMATIVE_INDEX.json`.

The committed index binds every authority path to its exact Git blob identity. Validation recomputes that Git blob identity from local bytes and additionally emits a SHA-256 digest for every authority file plus an aggregate SHA-256 over the validated set. This dual binding allows repository-object identity and SHA-256 certification without rewriting predecessor specifications.

The core authority families are:

- source/static semantics and general V2 language: `TEV_SCRIPT_V2_LANGUAGE.md`;
- capability/filesystem boundary: `TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`;
- Program IR V4 computation: `TEV_SCRIPT_PROGRAM_IR_V4.md`;
- semantic-process source: `TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`;
- Program IR V5 semantic process: `TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS.md`;
- Total-Core 3.1: `TEV_SCRIPT_V31_TOTAL_CORE.md`;
- exact portable value/operational behavior inherited by compatible profiles: the IR V3 value and operational-semantics specifications;
- checkpoint/restart behavior: `TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md`;
- canonical JSON: `CANONICAL_JSON_PROFILE_V1.md`;
- signed update boundary: `TEV_SCRIPT_SIGNED_UPDATE_V2.md`.

## 4. Source and production boundary

`.tevs` source may be parsed, checked and compiled by compiler/tooling processes. Production runtimes execute validated canonical IR/artifacts only. No production runtime may gain authority to reinterpret `.tevs` source.

Compiler output must bind the source-semantic identity required by its profile. A runtime receiving malformed, incompatible or unbound IR fails closed.

## 5. Exact values

Integer and rational arithmetic is exact on every profile that inherits the portable exact-value contract. Approximation or host-native floating conversion is a physical/host boundary and must be explicit.

Canonical serialization must reject non-canonical or non-finite host values when the target schema does not permit them.

## 6. Effects and capabilities

Source declarations and IR effect descriptions do not grant physical authority. Every physical effect crosses an explicit capability/provider boundary.

The observed effect/capability set of an execution must be a subset of the authority granted to that execution. Missing capability authority fails closed.

## 7. Bounded computation

Finite profiles obey their declared resource bounds. Contracted recursion, task execution and Total-Core quanta may not silently exceed those bounds.

Open-ended computation is represented only by continuation-linked finite quanta where the corresponding profile permits it. Resource exhaustion is an explicit deterministic outcome, not implicit unbounded execution.

## 8. Total-Core composition

`total_core` composes validated V4 child computation with the V5 Field/Transformation/Apply semantic process. Embedded V4 units retain their exact V4 program identity and are not reinterpreted by V5.

Proof admission remains external evidence. Physical effect commit remains outside pure runtime execution. Failure of a child validation, proof admission or identity binding fails the current operation closed.

## 9. Canonical identity and replay

Every content-addressed program, unit, checkpoint, continuation or receipt must be validated before authority is derived from it. Hash mismatch is terminal for that validation path.

Given the same validated program, checkpoint, explicit observations and granted capability inputs, conforming runtimes must produce the same canonical semantic result/receipt for the portable profile.

## 10. Cross-runtime conformance

A runtime is conforming only for the profiles explicitly listed in the version matrix and conformance manifest. Missing runtime support is `HOLD`/unsupported; it is never inferred `PASS`.

Cross-runtime comparison is performed on canonical values/bytes/hashes rather than host object formatting.

## 11. Version compatibility

Language version, source profile, linked-program schema, Program IR version, runtime ABI, checkpoint version and package version are independent version domains. Numeric equality alone never establishes compatibility.

`spec/TEV_SCRIPT_VERSION_MATRIX.json` is the machine-readable compatibility authority once present in the platform-completion candidate. Authority paths and implementation entrypoints are resolved against the exact checkout root being validated; availability from another installed checkout is not compatibility evidence.

## 12. Failure semantics

At every platform boundary, absence of required authority or evidence is fail-closed. In particular:

```text
missing capability          -> HOLD/FAIL
exhausted budget            -> explicit bounded failure
malformed IR/schema         -> FAIL
hash mismatch               -> FAIL
unsupported profile         -> HOLD/FAIL
missing proof admission     -> PROOF_REQUIRED/HOLD
runtime divergence          -> FAIL
missing conformance witness -> HOLD/FAIL
invalid child receipt       -> FAIL
evidence-set mismatch       -> FAIL
source-identity mismatch    -> FAIL
full regression failure     -> FAIL
full regression skip        -> FAIL
```

No `HOLD` state may be promoted to `PASS` by the aggregate platform-completion gate.

## 13. Completion condition

The platform-completion candidate is admitted only when the following independent gates all pass on one exact commit/tree:

```text
VERSION_IDENTITY
NORMATIVE_SPEC
VERSION_MATRIX
TOOLING_3X
CONFORMANCE
DIFFERENTIAL_FUZZ
SEMANTIC_INVARIANTS
REPRODUCIBLE_RELEASE
FULL_REGRESSION
```

`REPRODUCIBLE_RELEASE=PASS` is valid inside the aggregate only when its sealed receipt is valid and binds exactly the same:

```text
version_identity_sha256 = SHA256(canonical VERSION_IDENTITY receipt)
normative_set_sha256    = NORMATIVE_SPEC.normative_set_sha256
conformance_sha256       = CONFORMANCE.receipt_sha256
```

`FULL_REGRESSION` is the final certification guard. It MUST execute a non-empty full repository test suite and MUST report zero failures, zero errors and zero skips. The worktree MUST be clean before and after execution, and HEAD/tree MUST remain unchanged. Its sealed receipt MUST validate before aggregate authority is derived from it.

The source identity bound by `FULL_REGRESSION` MUST equal the source identity bound by `REPRODUCIBLE_RELEASE`. A specialized gate cannot substitute for this repository-wide non-regression requirement, and receipts from different source identities or different evidence sets cannot be composed into one completion claim.

Only the conjunction of all nine gates under these bindings may emit `PLATFORM_COMPLETION=PASS`. The aggregate receipt itself is content-addressed and externally verifiable. This condition does not grant merge, publication, tagging or stable-promotion authority.
