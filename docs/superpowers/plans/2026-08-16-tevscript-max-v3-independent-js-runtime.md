# TEVScript MAX V3 Independent JavaScript Runtime Implementation Plan

> **For agentic workers:** TDD is mandatory. Observe RED before implementation.

**Goal:** Add a dependency-free independent Node runtime for Program IR V5 and require byte-identical parity with Python.

**Architecture:** `runtime_js_v3/runtime_v5_semantic.mjs` is a standalone strict JSON validator/runtime. `tests/test_runtime_v5_js_parity.py` constructs canonical Python IR/checkpoints and compares raw canonical JSON output with the independent JS result.

### Task 1 — RED parity harness
- halted transformation with Unicode and `result_profile`;
- two-epoch cyclic suspension;
- tampered program hash rejection;
- duplicate JSON member rejection;
- `__proto__`/constructor spellings remain ordinary canonical data.

### Task 2 — GREEN canonical JSON + strict parser
Implement dependency-free strict parser and Python-compatible canonical encoder/hash.

### Task 3 — GREEN IR/checkpoint validation and runtime
Implement exact Field/Transformation/Apply, instructions, Omega continuation and quantum-result semantics.

### Task 4 — Authority/certification integration
Add runtime and parity test to V3 governed matrix; require Node parity in technical and Stable Admission gates; publish the exact `.mjs` runtime beside the V3 wheel.
