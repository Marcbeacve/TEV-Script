# TEV Script V1 artifact commit policy

Policy id:

```text
EVIDENCE_SAFE_RECEIPT_LAST_V1
```

Status: build/evidence tooling contract for the V1 implementation candidate.

Implementation:

```text
tev_script/artifact_write_v1.py
```

## Problem

A governed compilation may emit two related files:

```text
program.ir.json
program.lowering-receipt.json
```

The receipt asserts a relationship between canonical V1 linked semantics and the exact target IR.

Writing the receipt first is unsafe:

```text
old IR
new receipt
process fails before new IR write
```

The filesystem would then expose evidence apparently describing target bytes that are not present.

Writing IR first is safer, but replacing an existing pair also requires invalidating the old receipt before the IR changes. Otherwise a process crash can temporarily expose:

```text
new IR
old receipt
```

which is also a false evidence pairing.

## Commit ordering

When both IR and receipt are requested, the V1 writer performs:

```text
1. stage and fsync complete new IR bytes
2. stage and fsync complete new receipt bytes
3. move existing receipt away from authoritative receipt path
4. move existing IR away from authoritative IR path
5. atomically install new IR at IR path
6. atomically install new receipt at receipt path
7. delete old backups
```

Steps 3–6 use same-directory `os.replace` operations.

The receipt is therefore the **final commit witness**.

## Crash semantics

The policy does not claim an impossible property:

```text
hardware-atomic two-file transaction across arbitrary filesystems
```

An abrupt process/power failure can leave an authoritative path temporarily missing and a `.tev-backup-*` entry requiring recovery.

The required evidence-safety invariant is narrower and useful:

> After invalidating the prior receipt, the authoritative receipt path is not populated again until the new IR is already installed.

Therefore a crash may produce absence/incompleteness, but the commit order does not intentionally produce an old receipt attesting to new IR or a new receipt attesting to old IR.

## Normal exception semantics

For ordinary Python exceptions during commit:

```text
new receipt removed if installed
old receipt restored if present
new IR removed if installed
old IR restored if present
staging/backups cleaned
```

If rollback itself fails, the operation raises a distinct:

```text
TEVS_V1_ARTIFACT_ROLLBACK
```

rather than reporting a normal compilation failure.

## Single-artifact writes

`link` and other one-file V1 outputs use the same staging/replace/rollback primitive without a receipt pairing.

## Path collision

IR and receipt may not be the same authoritative path.

Failure:

```text
TEVS_V1_ARTIFACT_PATH_COLLISION
```

## Canonical newline

Text artifacts are persisted as UTF-8 with exactly one final LF after trimming repeated trailing LFs from the supplied canonical content.

This output newline is transport/file framing; semantic hashes are computed from each artifact's canonical JSON contract before file framing where defined.

## Tests

`tests/test_v1_artifact_write.py` covers:

- single-file replacement;
- successful paired IR+receipt commit;
- output-path collision;
- forced receipt-install failure with previous IR/receipt;
- rollback to exact previous file contents;
- failure with no previous artifacts leaving neither authoritative path;
- staging/backup cleanup.

The CLI tests additionally prove semantic compilation failure occurs before any requested IR/receipt output is created.
