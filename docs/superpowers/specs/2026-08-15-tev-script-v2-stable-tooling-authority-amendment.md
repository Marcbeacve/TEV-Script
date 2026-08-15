# TEV Script V2 Stable Tooling Authority — Design Amendment

Date: 2026-08-15

## Decision

Phase T keeps the historical V2 `authority_files` boundary unchanged. The Stable Admission machinery is governed by a separate closed `stable_tooling_authority` list, mirroring V1's separation between language authority and build/release tooling authority.

This supersedes the Phase-T plan sentence that proposed adding the three new receipt schemas directly to `authority_files`.

## Rationale

`authority_files` already identifies the normative V2 language/spec/schema set bound by the historical `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1`. Adding release-tooling receipts to that list would silently recategorize historical evidence and force unrelated authority tests to change.

Stable tooling is additive rather than semantic. It must be independently inspectable and certified, but it must not retroactively alter the meaning of the original V2 technical receipt.

## Closed tooling authority

The Phase-T canonical index and V2 feature matrix must contain exactly this tooling authority:

```text
tev_script/release_metadata_v2.py
tools/v2_certification_support.py
schemas/tev-script-v2-certify-full-receipt-v2.schema.json
RUN_TEV_SCRIPT_V2_PYTHON_CERTIFY_FULL.py
schemas/tev-script-v2-python-certify-full-receipt.schema.json
tools/validate_v2_stable_governance.py
RUN_TEV_SCRIPT_V2_STABLE_ADMISSION.py
schemas/tev-script-v2-stable-admission-receipt.schema.json
tools/validate_v2_stable_tooling_authority.py
```

`tools/validate_v2_stable_tooling_authority.py` validates exact inventory equality, path existence, all three new JSON schemas, gate bindings, release metadata profile coherence, and `stable_release_surface.stable_claim == release_metadata.STABLE`.

## Receipt compatibility

The historical `TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V1` gate map is unchanged.

`TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2` adds one technical witness:

```text
stable_tooling_authority = PASS
```

Thus only current-base technical certification attests the new tooling layer.

## Phase-T documentation scope

Phase T does not modify V1 release documents merely to announce tooling. The design, implementation plan, this amendment, canonical index, and V2 feature matrix are sufficient Phase-T authority. `README.md`, `CHANGELOG.md`, and `PROJECT_STATE.md` remain release-only inputs for Phase S, where the stable-shaped claim is actually formed. This avoids unnecessary V1 stable-governance churn.

## Invariants retained

- V2 remains `stable=false` throughout Phase T.
- Python distribution remains `1.0.0`.
- Language version remains `2.0.0`.
- No stable tag, release, PR, merge, or `LANGUAGE_STABLE=YES` is implied by Phase T.
- Phase S still permits exactly six release paths and cannot modify tooling, schemas, tests, parser, IR, runtime, filesystem safety, or package version.
