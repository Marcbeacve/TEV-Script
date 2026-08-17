# TEVScript Platform Completion — Full Regression Plan

## Objective

Close the repository-wide non-regression gap discovered after implementing the eight specialized platform gates.

## Tasks

1. Add `platform_regression.py` with a deterministic pytest/JUnit runner.
2. Require a non-empty suite with zero failures, errors and skips.
3. Bind clean worktree and HEAD/tree identity before and after regression.
4. Add `FULL_REGRESSION` as the ninth and final aggregate gate.
5. Require exact source identity equality with `REPRODUCIBLE_RELEASE`.
6. Preserve child receipt seals by wrapping aggregate policy failures.
7. Add receipt verifiers and Draft 2020-12 schemas.
8. Update normative completion authority and content-addressed normative index.
9. Synchronize current status/documentation.
10. Run the exact aggregate from a complete clean checkout before PR readiness or any completion claim.

## Verification command

```powershell
python .\RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py `
  --receipt .\TEV_SCRIPT_PLATFORM_COMPLETION_RECEIPT.json
```

Expected admission requires nine PASS values, `PLATFORM_COMPLETION=PASS`, one exact source commit/tree, and zero full-regression skips.
