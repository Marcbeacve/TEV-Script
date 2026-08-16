# TEVScript MAX V3 Source and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use TDD; observe RED before implementation.

**Goal:** Make MAX V3 directly programmable through a native semantic-process `.tevs` source profile and one V3 CLI while preserving unchanged V2 dispatch.

**Architecture:** `source_semantic_process_v3.py` parses/resolves the native V3 profile and lowers to Program IR V5. `cli_v3.py` provides `check`, `compile`, `run`, and `describe`; it detects V3 semantic-process headers or delegates unchanged V2 sources to existing V2 APIs. No V2 implementation file changes.

### Task 1 — RED/GREEN V3 parser and source identity

Test whitespace/comment invariance, order-independent fact/transform declarations, unique names, unknown refs, malformed JSON arguments, finite quantum bound, and source-hash tamper resistance.

### Task 2 — RED/GREEN IR V5 lowering

Test label resolution, canonical lexical label order, cyclic jump compilation, exact transform/fact references and compiled IR execution through `runtime_v5_semantic`.

### Task 3 — RED/GREEN CLI V3

Test `describe`, V3 `check/compile/run`, deterministic JSON output, invalid-source nonzero exit, and V2 dispatch preserving V2 identity.

### Task 4 — Regression

Run all MAX focal tests plus existing V2 source/CLI tests when the complete repository checkout is available.