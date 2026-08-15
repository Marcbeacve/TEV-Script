# TEV Script V2 Artifact Byte Identity — Design Amendment

Date: 2026-08-15

## Decision

`artifact_byte_identity_required` means byte identity inside one certification/admission evidence chain, not equality between the Phase-T technical-parent wheel and the Phase-S stable wheel.

For any V2 Python certification run, the following must all identify the same wheel bytes:

```text
V1 Python upstream receipt wheel_sha256
= physical exported wheel SHA-256
= V2 Python receipt wheel_sha256
= physical wheel SHA-256 rechecked by Stable Admission
```

The installed wheel must additionally expose a V2 descriptor whose `descriptor_hash` is exactly equal to the descriptor hash of the checkout being certified.

## Why parent-wheel equality is not the invariant

Phase S intentionally changes `tev_script/release_metadata_v2.py` from candidate state to stable state. The deterministic Python backend packages every `.py` module under `tev_script`, so the Phase-S wheel necessarily differs byte-for-byte from the Phase-T/parent wheel even though the Python distribution version remains `1.0.0`.

Therefore this would be contradictory and is explicitly **not** required:

```text
SHA256(parent_candidate_wheel) == SHA256(stable_release_wheel)
```

The invariant is instead:

```text
source identity S
-> deterministic wheel W(S)
-> upstream V1 Python receipt binds W(S)
-> V2 Python receipt binds the same W(S)
-> isolated install proves W(S) exposes the exact V2 descriptor of S
-> Stable Admission re-hashes the same W(S)
```

## Package-version interpretation

Python package version `1.0.0` is a compatibility/versioning authority, not a claim that two separately built repository states must have identical wheel bytes. Phase S does not modify `pyproject.toml`; it changes only release metadata embedded in the package.

A future distribution-version change remains a separate project and is not implied by V2 language stability.

## Stable Admission implication

The existing `artifact_byte_identity_required=true` surface is satisfied when Stable Admission proves all of the following for its own stable checkout:

- upstream V1 Python receipt commit/tree/branch equals the stable checkout;
- wheel filename/package identity are exact;
- physical wheel SHA equals the upstream V1 Python receipt SHA;
- V2 Python receipt records that same SHA;
- isolated wheel install comes from the venv and exposes the exact checkout `descriptor_hash`;
- Stable Admission re-hashes the wheel and obtains the same SHA before issuing its receipt.

No parent-wheel byte comparison is part of this invariant.
