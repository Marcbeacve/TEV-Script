# TEV Script V1 / IR V3 current validation witness

Date: 2026-08-08
Branch: `agent/tev-script-v1-irv3-spec-v1`
Certified historical oracle preserved: `6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5` (V0.2)

## Fresh execution performed

The exact public branch archive was materialized into an isolated local runtime and validated without GitHub Actions.

### Python V1/V3 closure gate

Command authority: `RUN_TEV_SCRIPT_V1_FRONTEND_CLOSURE.py`.

Observed required witnesses:

```text
TEV_SCRIPT_V1_PYTHON_COMPILE=PASS
TEV_SCRIPT_V1_TESTS=PASS
TEV_SCRIPT_IR_V3_TESTS=PASS
TEV_SCRIPT_V0_2_PYTHON_REGRESSION=PASS
TEV_SCRIPT_V1_PYTHON_CLOSURE=PASS_CANDIDATE
```

The unittest execution reported no skipped tests in this environment.

### Cross-runtime IR V3 byte lock

Command authority: `tools/validate_ir_v3_cross_runtime_parity.py`.

Observed required witnesses:

```text
TEV_SCRIPT_IR_V3_NODE_TESTS=PASS
TEV_SCRIPT_IR_V3_CSHARP_BUILD=PASS
TEV_SCRIPT_IR_V3_CSHARP_SELF_TEST=PASS
TEV_SCRIPT_IR_V3_PYTHON_JS_PARITY=PASS
TEV_SCRIPT_IR_V3_PYTHON_CSHARP_PARITY=PASS
TEV_SCRIPT_IR_V3_JS_CSHARP_PARITY=PASS
TEV_SCRIPT_IR_V3_CROSS_RUNTIME_CANONICAL_BYTES=PASS
TEV_SCRIPT_IR_V3_CROSS_RUNTIME_PARITY=PASS
```

This proves, for the shared algebraic V3 conformance program/scenario currently in the repository, that Python, JavaScript and C# produce byte-identical canonical execution receipts after the C# runtime passes the shared negative validator corpus.

## What this closes

- Python V1 frontend/link/static/constant/behavior candidate execution.
- `TEV_SCRIPT_LINKED_PROGRAM_V1` candidate generation and schema campaign.
- V1 erasable path to certified IR V2 candidate lowering.
- Full V1 algebraic path to IR V3 candidate lowering.
- IR V3 record/enum/Option/Result canonical value model.
- IR V3 typed forward-only CFG verification.
- Python IR V3 runtime candidate.
- JavaScript IR V3 runtime candidate against shared corpus.
- C# IR V3 runtime candidate against shared corpus.
- Python/JavaScript/C# byte-identical IR V3 conformance receipt for the shared scenario.
- V0.2 Python regression preservation in the same fresh campaign.

## What this does NOT close

This witness does **not** authorize `LANGUAGE_STABLE=YES` or V1 release promotion.

Still pending before stable V1:

1. exact clean-commit/tree certification for the complete V1 candidate;
2. complete JavaScript and C# V1 source frontend/link/static-semantic parity if V1 source compilation is required on those hosts rather than using the canonical linked-program artifact as the compiler/runtime boundary;
3. checkpoint/restart V2 byte parity across JavaScript and C#;
4. Browser-WASM IR V3 runtime/parity campaign;
5. WASI IR V3 runtime/parity campaign;
6. V1 signed-update/checkpoint interaction across the IR V3 profile;
7. complete promotion-gate replay from one exact immutable commit.

## Architectural conclusion

The current cross-host authority boundary is now viable as:

```text
V1 source set
  -> deterministic linked semantic program
  -> IR V2 (erasable profile) OR IR V3 (full algebraic profile)
  -> Python / JavaScript / C# runtime
  -> canonical conformance receipt
```

The important remaining design decision is therefore not another source-language feature. It is whether JavaScript/C# must independently compile V1 source or whether `TEV_SCRIPT_LINKED_PROGRAM_V1` is the normative portable compiler/runtime handoff. Until that decision is frozen and the remaining host campaigns pass, V1 remains an implemented candidate rather than a stable release.
