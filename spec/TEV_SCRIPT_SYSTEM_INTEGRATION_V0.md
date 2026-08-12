# TEV Script System Integration V0

Status: **post-V1 integration contract; additive and non-normative for TEV Script V1 language semantics**.

## 1. Purpose

A consumer that needs TEV Script as a complete subsystem must consume the TEV Script distribution, not copy individual language, causal, semantic, realization, runtime, compiler or verifier modules into the consumer.

The integration boundary is:

```text
TEV Script distribution
  -> versioned system API contract
  -> exact integration receipt
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
TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0
```

The language version identifies the governed TEV Script language contract. The system API contract hash identifies the additive integration surface. The artifact SHA-256 identifies the exact installed bytes. The integration receipt binds those identities to source HEAD/TREE and the integration gates that admitted the artifact.

Package version text alone is insufficient to identify an experimental post-V1 system artifact.

## 3. Complete-system boundary

`tev_script.system_api_v0` is the opt-in consumer-facing facade for the complete Python-side system integration profile.

The complete profile covers:

```text
historical V0.2/V1 public Python API
language analysis / compilation / project tooling
IR V2 / IR V3 lowering
lowering receipts and verification
IR V3 validation / conformance / runtime / checkpoint
Python production host
Causal Reaction V1
Causal -> Semantic bridge
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
integration receipt construction and verification
complete post-V1 causal registry
complete post-V1 semantic subsystem registry
```

The wheel transports the implementation modules together, while the facade defines the governed consumer contract.

## 4. Stable public API preservation

The historical package root remains authoritative for its existing public Python surface:

```text
tev_script.__all__
```

The system facade MUST preserve that surface exactly as the `stable_public_api` system surface:

```text
system_api_contract_object_v0()["surfaces"]["stable_public_api"]
    == tev_script.__all__
```

Every historical public symbol MUST also exist in `SYSTEM_API_EXPORTS_V0`, and importing that symbol through `tev_script.system_api_v0` MUST yield the same Python object as importing it through `tev_script`.

Therefore:

```text
stable API identity
      +
post-V1 system additions
      =
system_api_v0
```

The facade is an additive supergraph. It does not redefine the historical package root.

The system integration receipt MUST explicitly contain:

```text
stable_public_api_preserved=PASS
```

Omission or degradation of that field makes the receipt invalid.

## 5. Closed causal and semantic registries

The direct high-level facade is not the entire module set. Completeness is closed by two registries:

```text
SYSTEM_CAUSAL_MODULE_PATHS_V0
load_system_causal_subsystem_v0(subsystem_id)

SYSTEM_SUBSYSTEM_MODULE_PATHS_V0
load_system_subsystem_v0(subsystem_id)
```

`SYSTEM_CAUSAL_MODULE_PATHS_V0` MUST contain exactly every `tev_script/causal_*_v1.py` module in the admitted source tree.

`SYSTEM_SUBSYSTEM_MODULE_PATHS_V0` MUST contain exactly every `tev_script/semantic_*.py` module in the admitted source tree.

Both registries are part of `SYSTEM_API_CONTRACT_HASH_V0`. Adding, deleting or renaming a governed causal or semantic subsystem without updating its registry makes the system gate fail closed.

The loaders accept only ids already present in their registries. A consumer therefore does not invent package paths to reach causal analysis/runtime/refinement, cost models, placement, dispatch, delivery, resource calibration, receipt validity, realization composition or other post-V1 layers.

The causal registry does not make Semantic Calculus the authority of Causal Reaction or vice versa. Their one-directional bridge and independent authorities remain unchanged.

## 6. Authority direction

The required dependency direction is:

```text
consumer
   -> TEV Script system API
        -> TEV Script-owned language / causal / semantic / runtime authorities
```

Forbidden direction:

```text
TEV Script authority
   -> consumer project
```

TEV Script MUST NOT import consumer-specific packages, paths, policies, models, agents or release state in order to define or execute its semantics.

External metatheories and provers remain optional evidence providers only. They are not runtime, build or semantic authorities.

## 7. Fail-closed integration

A consumer MUST preserve TEV Script outcomes without upgrading them:

```text
PROOF_REQUIRED -> not PASS
REJECT         -> not PASS
INDETERMINATE  -> not SELECTED
NO_ADMISSIBLE_REALIZATION -> not implicit fallback
```

A consumer MAY request additional evidence, search additional candidates or provide an explicit selection policy. It MUST NOT forge a successful receipt by replacing an unresolved result with a local heuristic.

## 8. Governed realization resolution

Automatic realization resolution is distinct from validating a caller-supplied decision.

The resolver may return only:

```text
SELECTED
INDETERMINATE
NO_ADMISSIBLE_REALIZATION
```

`SELECTED` requires a unique decision that passes the existing selection verifier.

For `PARETO_MEMBER`, multiple non-dominated admissible candidates produce:

```text
INDETERMINATE
selection.preference_required
```

For tied `LEXICOGRAPHIC_MIN` candidates:

```text
INDETERMINATE
selection.lexicographic_tie
```

Open admission/evidence obligations remain `PROOF_REQUIRED` and prevent a fabricated resolution.

`NO_ADMISSIBLE_REALIZATION` is a successful resolution of the question "is there an admitted realization?"; it is not permission to choose an unadmitted fallback.

## 9. Backend neutrality

Backend/provider identity is realization metadata, not Transformation semantic identity.

A consumer MUST select or replace backends only through admitted realization/equivalence boundaries. It MUST NOT encode semantic branches such as:

```text
if backend == python: semantics A
if backend == wasm: semantics B
```

unless the requested Transformation itself explicitly makes that distinction semantically observable.

## 10. Exact artifact binding

The system API hash does not replace artifact integrity. A deployment binds the exact installed wheel/archive SHA-256 independently.

The canonical handoff record is:

```text
TEV_SCRIPT_SYSTEM_INTEGRATION_RECEIPT_V0
```

Its implementation and verifier live in:

```text
tev_script/system_integration_receipt_v0.py
```

A consumer verifies the receipt using the installed TEV Script distribution itself:

```python
verify_system_integration_receipt_v0(
    receipt,
    expected_language_version=V1_LANGUAGE_VERSION,
    expected_system_api_contract_hash=SYSTEM_API_CONTRACT_HASH_V0,
    expected_distribution_artifact_sha256=wheel_sha256,
    expected_source_head=source_head,
    expected_source_tree=source_tree,
)
```

The verifier fails closed on schema/field-set changes, canonical receipt tampering, wrong API identity, wrong wheel SHA-256 or mismatched source identity.

## 11. System canonical index

The historical `CANONICAL_INDEX.json` remains the language/release authority and is not reinterpreted by this post-V1 system profile.

The additive system authority index is:

```text
spec/TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0.json
```

with schema:

```text
TEV_SCRIPT_SYSTEM_CANONICAL_INDEX_V0
```

It binds the system facade, stable-public-API preservation, closed causal and semantic registries, receipt contract, realization/host/action-loop implementation surfaces and all integration gates while preserving `stable=false` for the post-V1 system profile.

## 12. Stable V1 root remains unchanged

This integration profile is intentionally not injected into the historical unversioned package root. Consumers opt into:

```python
import tev_script.system_api_v0
```

`tev_script/__init__.py`, language semantics, release metadata and historical V1 identity are not rewritten by this integration profile.

## 13. Distribution rule

The in-tree wheel backend packages all Python modules under `tev_script/`. Therefore the historical public API implementation, system facade, causal and semantic subsystems, receipt verifier and implementation modules are transported together by a wheel built from the same source identity.

A production consumer MUST pin the exact wheel bytes. Distribution/package version remains insufficient as a post-V1 system identity by itself; `SYSTEM_API_CONTRACT_HASH_V0` plus exact artifact SHA-256 and the integration receipt close that ambiguity.

A later public post-V1 release may introduce a distinct distribution version/profile, but that release operation is outside this V0 integration contract.

## 14. Exact artifact admission

`RUN_TEV_SCRIPT_SYSTEM_INTEGRATION_V0.py` is the exact-artifact integration gate. It does not publish, merge, tag, promote, mutate `Current` or modify a consumer.

The gate requires a clean named-branch checkout and an empty output directory outside the repository. It:

```text
runs the system focal
  -> validates system API contract
  -> proves stable_public_api preservation
  -> proves source causal registry is non-empty and closed
  -> proves source semantic registry is non-empty and closed
  -> builds two independent deterministic wheels
  -> requires byte identity between both builds
  -> installs exact wheel into a clean venv with --no-deps
  -> imports complete system API from installed wheel
  -> loads every registered Causal Reaction V1 module
  -> loads every registered semantic subsystem
  -> requires installed/source registry cardinality identity
  -> constructs canonical integration receipt
  -> makes installed wheel verify that receipt
  -> copies exact wheel to output directory
  -> copies receipt last
```

The receipt is the final admission artifact. A wheel without its matching admitted receipt is not a complete system handoff.

## 15. Readiness gate

A candidate is ready for external-system integration only when focal and exact-artifact gates prove:

```text
SYSTEM_API_IMPORT_BOUNDARY=PASS
SYSTEM_STABLE_PUBLIC_API_PRESERVATION=PASS
SYSTEM_API_CONTRACT_HASH=PASS
SYSTEM_API_REQUIRED_SURFACE=PASS
SYSTEM_COMPLETE_CAUSAL_REGISTRY_CLOSED=PASS
SYSTEM_COMPLETE_SEMANTIC_REGISTRY_CLOSED=PASS
SYSTEM_CANONICAL_INDEX_SCHEMA=PASS
V1_ROOT_API_NOT_REDEFINED=PASS
SYSTEM_ZERO_RUNTIME_DEPENDENCIES=PASS
SYSTEM_CAUSAL_REACTION=PASS
SYSTEM_CAUSAL_SEMANTIC_BRIDGE=PASS
SYSTEM_WHEEL_DETERMINISTIC_BYTES=PASS
SYSTEM_INSTALLED_WHEEL_IMPORT=PASS
SYSTEM_INSTALLED_API_IDENTITY=PASS
SYSTEM_INSTALLED_COMPLETE_CAUSAL_REGISTRY=PASS
SYSTEM_INSTALLED_COMPLETE_SEMANTIC_REGISTRY=PASS
SYSTEM_INSTALLED_RECEIPT_VERIFIER=PASS
SYSTEM_ARTIFACT_RECEIPT_LAST=PASS
R2_INDETERMINACY_PRESERVED=PASS
R1_HOST_EVIDENCE_BOUNDARY_PRESENT=PASS
SYSTEM_ACTION_LOOP_BOUNDARY_PRESENT=PASS
TEV_SCRIPT_SYSTEM_INTEGRATION_ARTIFACT=PASS
```

The exact handoff consists of:

```text
<exact wheel>
TEV_SCRIPT_SYSTEM_INTEGRATION_V0.receipt.json
```

plus:

```text
SYSTEM_DISTRIBUTION_WHEEL_SHA256
SYSTEM_API_CONTRACT_HASH_V0
SYSTEM_INTEGRATION_RECEIPT_SHA256
SYSTEM_INTEGRATION_RECEIPT_FILE_SHA256
```

`CERTIFY_FULL`, cross-host long campaigns, public release/promotion and Unity validation remain separate final-stage obligations.
