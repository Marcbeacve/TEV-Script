# Status

## Current published line

```text
PACKAGE=tev-script-portable-reference
PUBLISHED_VERSION=3.1.0
PUBLISHED_PROFILE=total_core
PUBLISHED_TAG=v3.1.0
PUBLISHED_COMMIT=c20718ddb2223ba0bfd05ff59006ca31e2966b0b
PUBLISHED_TREE=812b140c5e6fb7232ef379773d9c37e8f3459f4c
PUBLISHED_STABLE_ADMISSION=PASS
PUBLISHED_PYTHON_JS_PARITY=PASS
```

The published `v3.1.0` Total-Core release remains immutable predecessor authority. This branch does not rewrite, retag or republish that release.

## Platform-completion candidate

Branch: `agent/tevscript-platform-completion-v1`

The candidate adds a fail-closed platform layer around the published 3.1 semantic core. The required aggregate gates are:

```text
VERSION_IDENTITY
NORMATIVE_SPEC
CONFORMANCE
DIFFERENTIAL_FUZZ
SEMANTIC_INVARIANTS
VERSION_MATRIX
TOOLING_3X
REPRODUCIBLE_RELEASE
```

Only eight simultaneous PASS results may produce:

```text
PLATFORM_COMPLETION=PASS
```

Implementation status:

```text
CANONICAL_CURRENT_VERSION_AUTHORITY=IMPLEMENTED
NORMATIVE_3_1_PLATFORM_SPEC=IMPLEMENTED
EXPLICIT_VERSION_MATRIX=IMPLEMENTED
VERSION_AWARE_TOOLING=IMPLEMENTED
FAIL_CLOSED_GENERIC_LSP=IMPLEMENTED
EXECUTABLE_3_1_CONFORMANCE_MANIFEST=IMPLEMENTED
DETERMINISTIC_DIFFERENTIAL_FUZZ=IMPLEMENTED
CONSTITUTIONAL_INVARIANT_WITNESSES=IMPLEMENTED
REPRODUCIBLE_WHEEL_SBOM_PROVENANCE=IMPLEMENTED
AGGREGATE_PLATFORM_COMPLETION_GATE=IMPLEMENTED
```

Development evidence for the isolated new platform layer:

```text
SYNTHETIC_TDD_TESTS=41_PASS
FULL_REPOSITORY_REGRESSION=NOT_EXECUTED_IN_CONNECTOR_ENVIRONMENT
PLATFORM_COMPLETION_CERTIFICATION=PENDING_FULL_REPOSITORY_EXECUTION
MERGE_AUTHORITY=FALSE
PUBLICATION_AUTHORITY=FALSE
TAG_AUTHORITY=FALSE
```

The connector/container used to implement this candidate cannot materialize the complete GitHub checkout because outbound DNS/download access is blocked. Therefore the 41-test isolated TDD campaign is development evidence only and MUST NOT be promoted to full-repository certification. Run `python RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py` from a complete clean checkout to obtain the aggregate authority receipt.

## Historical V0.2/V1 lineage

The following section is retained as historical evidence and is not the current version declaration:

```text
HISTORICAL_VERSION=0.2.0-preview
HISTORICAL_LANGUAGE_STABLE=NO

SIGNED_UPDATE_GATE5C=PASS_CERTIFIED
ANTI_REPLAY_GATE5D=PASS_CERTIFIED_WITH_DURABLE_STATE_BOUNDARY
REMOTE_TRANSPORT_GATE5E=PASS_CERTIFIED_LOOPBACK_HTTP_IL2CPP
UNITY_WEB_WASM_GATE6A=PASS_CERTIFIED
PURE_CORE_BROWSER_WASM_GATE6B=PASS_CERTIFIED_AOT
PURE_CORE_WASI_GATE6C=PASS_CERTIFIED_WASMTIME
SIGNED_WASM_UPDATE_GATE6D=PASS_CERTIFIED_BROWSER_AND_WASI

DETERMINISTIC_REPLAY_GATE7A=PASS_OBSERVED_LOCAL_PRECOMMIT
CROSS_HOST_LOCKSTEP_GATE7B=PASS_OBSERVED_LOCAL_PRECOMMIT
FIRST_DIVERGENCE_GATE7C=PASS_OBSERVED_LOCAL_PRECOMMIT
CANONICAL_CHECKPOINT_GATE7D=PASS_OBSERVED_LOCAL_PRECOMMIT
SIGNED_UPDATE_LOCKSTEP_GATE7E=PASS_OBSERVED_LOCAL_PRECOMMIT
```

Historical Gate-7 evidence and the V1 language-completeness records remain preserved in their original specifications, receipts and release tooling. They are compatibility/predecessor evidence, not the current 3.1 platform status.
