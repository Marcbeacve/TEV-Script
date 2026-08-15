# TEV Script V2 Canonical Parent Recertification — Design Amendment

Date: 2026-08-15

## Problem

Phase T is certified before publication and merge. If GitHub integrates the exact Phase-T candidate with a merge commit, the canonical `main` commit has a new SHA even when the merge tree is byte-identical to the certified candidate tree. Therefore the pre-merge Phase-T receipt cannot truthfully serve as the Phase-S technical-parent certificate for the canonical merge commit.

## Decision

Use two distinct receipts for two distinct authorities:

1. **Phase-T candidate receipt** — certifies the exact pre-merge Phase-T branch and authorizes only review/publication/merge of that exact technical candidate.
2. **Canonical-parent receipt** — after Phase T is merged and post-merge tree preservation is proven, create a zero-diff `agent/` branch pointing at the exact canonical `main` commit `P`. Run current-base V2 certification there with `--profile candidate --expected-base P`. Because the branch ref and `main` point to the same commit, the receipt binds `commit_sha=P`, `tree_sha=P^{tree}`, and `base_sha=P`.

Phase S may consume only the second receipt.

## Stable Admission strengthening

The V2 Stable Admission parent-certificate loader must require all of:

```text
schema             = TEV_SCRIPT_V2_CERTIFY_FULL_RECEIPT_V2
admission_profile  = candidate
commit_sha          = P
tree_sha            = P^{tree}
base_sha            = P
dirty               = false
certify_full        = true
language_stable     = false
receipt_hash        = declared TECHNICAL_PARENT_CERTIFICATE_SHA256
```

Requiring `base_sha == commit_sha == P` makes a pre-merge candidate receipt structurally inadmissible as a canonical stable parent receipt.

## Canonical-parent recertification procedure

After Phase-T merge and post-merge verification:

```text
main = P
create local branch agent/tev-script-v2-stable-parent-cert-v1 at P
fetch origin/main
require HEAD == origin/main == P
require clean worktree
run RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --profile candidate --expected-base P
freeze external receipt hash
```

This branch contains no source diff and does not need to be published merely to produce the local receipt.

## Phase-S start condition

Phase S does not begin until both are available:

```text
P      = exact canonical main commit after Phase-T merge
P_CERT = canonical-parent V2 receipt whose commit_sha == base_sha == P
```

The stable release branch is then created from `P` and may change only the six release-only paths defined by the Stable Admission design.
