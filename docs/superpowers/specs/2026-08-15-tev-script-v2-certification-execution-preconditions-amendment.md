# TEV Script V2 Certification Execution Preconditions — Design Amendment

Date: 2026-08-15

## Decision

A current-base V2 receipt is valid only when the local remote-tracking base is freshly synchronized immediately before certification and the certifying process has exclusive control of the selected worktree and evidence directory for the duration of the gate.

This amendment makes explicit assumptions that were previously implicit in `collect_git_identity()`.

## Fresh remote-base precondition

`collect_git_identity()` proves:

```text
origin/main == expected_base
expected_base is ancestor of HEAD
HEAD/tree/branch are exact
worktree is clean
```

`origin/main` is a local remote-tracking ref. It is not by itself proof that the remote server has not advanced since the last fetch.

Therefore every current-base certification run must be preceded immediately by:

```text
git fetch origin main --prune
git rev-parse --verify origin/main
```

and the observed `origin/main` must equal the exact `--expected-base` supplied to the gate.

If the fetch fails, if the remote-tracking ref differs, or if `main` advances before the certification run is started, the run is not admissible. Do not substitute a cached ref or an assumed SHA.

The certifier itself remains deterministic with respect to the already-refreshed Git state; it does not silently mutate repository refs by fetching during certification.

## Exclusive-worktree precondition

The clean-before/clean-after identity checks protect against ordinary accidental changes. They do not attempt to defend against another same-user process deliberately modifying tracked files during a gate and restoring the exact tree before the final identity check.

Certification therefore requires exclusive control of the selected worktree during the run:

```text
no editor/formatter writing files
no second test/certification process mutating the worktree
no checkout/reset/rebase/merge during the run
no generator writing tracked files
```

A detected concurrent mutation invalidates the run even if the final Git tree happens to match the initial tree again.

## External evidence precondition

Receipt outputs must use new external paths and artifact outputs must use new empty external directories. Evidence from a previous run is never overwritten or silently reused.

Where V2 gates emit receipts, create-once semantics are the target contract. Artifact files that are inspected more than once must be snapshot/hash bound or re-hashed before the receipt is issued.

## Phase-T invocation order

Before Phase-T certification:

```text
git fetch origin main --prune
require origin/main == fef64edf903610b87a1dc959ef7cbf7ab9f5400f
require clean exclusive agent/ worktree
run full regression / V1 / V2 / V2 Python gates
```

If `main` has moved, stop and reassess/rebase under the project governance instead of certifying against stale `P0`.

## Canonical-parent recertification order

After Phase T is later merged, let the exact canonical merge commit be `P`.

Before producing `P_CERT`:

```text
git fetch origin main --prune
require origin/main == P
create/use a zero-diff local agent/ branch at P
require HEAD == P
require clean exclusive worktree
RUN_TEV_SCRIPT_V2_CERTIFY_FULL.py --profile candidate --expected-base P
```

Thus the parent certificate cannot be based on a stale view of canonical `main`.

## Phase-S Stable Admission order

Before Stable Admission on S:

```text
git fetch origin main --prune
require origin/main == P
require P remains the declared technical parent
require clean exclusive S worktree
require a fresh empty external artifact directory
run Stable Admission
```

If canonical `main` advances away from P before S is promoted, publication/merge requires a new governance decision; Stable Admission does not silently retarget its parent.
