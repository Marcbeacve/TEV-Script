# TEVScript Platform Completion — Full Regression Amendment

Date: 2026-08-17
Status: approved implementation amendment
Supersedes: only the aggregate-completion gate count in `2026-08-17-tevscript-platform-completion-design.md`.

## Reason

The original platform-completion design required eight specialized gates. During implementation review, a falsifiable gap was found: all eight specialized gates could theoretically pass while an unrelated historical repository test failed outside the conformance/invariant witness sets.

That would make `PLATFORM_COMPLETION=PASS` stronger than its evidence.

## Amendment

Add one final independent gate:

```text
FULL_REGRESSION
```

The complete aggregate order becomes:

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

`FULL_REGRESSION=PASS` requires:

```text
pytest return code = 0
test_count > 0
failure_count = 0
error_count = 0
skipped_count = 0
worktree clean before = true
worktree clean after = true
HEAD before = HEAD after
TREE before = TREE after
```

The JUnit result is content-addressed. The full-regression receipt is sealed and externally verifiable.

## Cross-gate identity rule

A second gap was found during the amendment: the reproducible wheel and full regression could otherwise be produced from different source identities.

Therefore:

```text
REPRODUCIBLE_RELEASE.source_commit
    == FULL_REGRESSION.source_commit

REPRODUCIBLE_RELEASE.source_tree
    == FULL_REGRESSION.source_tree
```

Any absence or mismatch is FAIL.

Policy failures wrap child receipts instead of mutating them, preserving child receipt seals.

## Aggregate receipt

The aggregate receipt advances to:

```text
TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT_V2
```

It binds:

```text
nine gate outcomes
exact source commit/tree
full-regression receipt SHA-256
full-regression test count
aggregate receipt SHA-256
```

It has a dedicated verifier and Draft 2020-12 schema.

## Non-authority

This amendment does not grant merge, tag, publication or stable-promotion authority. It only strengthens the evidence required before platform completion can be claimed.
