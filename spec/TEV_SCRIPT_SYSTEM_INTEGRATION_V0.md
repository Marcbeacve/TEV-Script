# TEV Script System Integration V0

Status: **post-V1 integration contract; additive and non-normative for TEV Script V1 language semantics**.

## 1. Purpose

A consumer that needs TEV Script as a complete subsystem must consume the TEV Script distribution, not copy individual realization, runtime, compiler or verifier modules into the consumer.

The integration boundary is:

```text
TEV Script distribution
  -> versioned system API contract
  -> consumer
```

The consumer is not a TEV Script semantic authority.

## 2. Identity

V1 language identity and post-V1 system integration identity are separate.

A consumer MUST bind all of:

```text
V1_LANGUAGE_VERSION
SYSTEM_API_CONTRACT_HASH_V0
exact distribution artifact SHA-256
```

The language version identifies the governed TEV Script language contract. The system API contract hash identifies the additive integration surface. The artifact SHA-256 identifies the exact installed bytes.

Package version text alone is insufficient to identify an experimental post-V1 system artifact.

## 3. Complete-system boundary

`tev_script.system_api_v0` is the consumer-facing facade for the complete Python-side system integration profile. The wheel continues to contain the implementation modules; the facade defines which high-level surfaces a consumer may bind without importing private implementation layout as its contract.

The facade covers:

```text
language analysis / compilation
IR V2 / IR V3 lowering
IR V3 lowering receipts and verification
IR V3 validation / conformance / runtime / checkpoint
Field + Transformation semantic calculus
artifact / evidence / machine / regime / resource descriptions
realization admission
Pareto and governed selection
selection resolution with explicit indeterminacy
search coverage and planning evaluation
provider-neutral host realization and host evidence
execution request governance
activation
execution observation
grounded discovery after execution
```

## 4. Authority direction

The required dependency direction is:

```text
consumer
   -> TEV Script system API
        -> TEV Script-owned semantic/runtime authorities
```

Forbidden direction:

```text
TEV Script authority
   -> consumer project
```

TEV Script MUST NOT import consumer-specific packages, paths, policies, models, agents or release state in order to define or execute its semantics.

## 5. Fail-closed integration

A consumer MUST preserve TEV Script outcomes without upgrading them.

In particular:

```text
PROOF_REQUIRED -> not PASS
REJECT         -> not PASS
INDETERMINATE  -> not SELECTED
NO_ADMISSIBLE_REALIZATION -> not implicit fallback
```

A consumer MAY request additional evidence, search additional candidates or provide an explicit selection policy. It MUST NOT forge a successful TEV Script receipt by replacing an unresolved result with a local heuristic.

## 6. Backend neutrality

Backend/provider identity is realization metadata, not Transformation semantic identity.

A consumer MUST therefore select or replace backends only through admitted realization/equivalence boundaries. It MUST NOT encode semantic branches such as:

```text
if backend == python: semantics A
if backend == wasm: semantics B
```

unless the requested Transformation itself explicitly makes that distinction semantically observable.

## 7. Exact artifact binding

The system API hash does not replace artifact integrity. A deployment binds the exact installed wheel/archive hash independently.

Recommended consumer record:

```text
TEV_SCRIPT_SYSTEM_BINDING_V0
  language_version
  system_api_contract_hash
  distribution_name
  distribution_version
  distribution_artifact_sha256
  optional source_commit
  optional source_tree
```

Repository commit/tree provenance is useful for reconstruction but does not replace the artifact SHA-256 consumed at runtime.

## 8. Stable V1 root API remains unchanged

This integration profile is intentionally not injected into the historical unversioned package root. Consumers opt into:

```python
import tev_script.system_api_v0
```

This prevents an additive post-V1 integration surface from silently redefining the already governed V1 package root.

## 9. Distribution rule

The in-tree wheel backend packages all Python modules under `tev_script/`. Therefore the system facade and its implementation modules are transported together by a wheel built from the same source identity.

A production consumer MUST pin the exact wheel bytes. A later public post-V1 release may introduce a distinct distribution version/profile, but that release operation is outside this V0 integration contract.

## 10. Readiness gate

A candidate is ready for external-system integration only when the focal integration gate proves:

```text
SYSTEM_API_IMPORT=PASS
SYSTEM_API_CONTRACT_HASH=PASS
SYSTEM_API_REQUIRED_SURFACES=PASS
V1_ROOT_API_NOT_REDEFINED=PASS
ZERO_RUNTIME_DEPENDENCIES=PASS
SYSTEM_WHEEL_INCLUDES_TEV_SCRIPT_PYTHON_MODULES=PASS
NO_CONSUMER_AUTHORITY_IMPORT=PASS
NO_BACKEND_SEMANTIC_AUTHORITY=PASS
R2_INDETERMINACY_PRESERVED=PASS
R1_HOST_EVIDENCE_BOUNDARY_PRESENT=PASS
ACTION_LOOP_BINDING_PRESENT=PASS
LONG_VALIDATION_DEFERRED=PASS
```

`CERTIFY_FULL`, cross-host campaigns and public release/promotion remain separate final-stage obligations.
