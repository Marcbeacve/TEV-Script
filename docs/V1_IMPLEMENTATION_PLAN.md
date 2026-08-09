# TEV Script V1 implementation plan

This plan starts from the certified V0.2 language-completeness commit `6e102f3cc3dcd131ae11e0cfc8bcfe64cccf87f5`. The V0.2 compiler/runtime path remains a regression oracle; V1 work is additive until parity is proven.

## Objective

Implement the complete V1 source contract without weakening V0.2 determinism, portability, boundedness or fail-closed authority semantics.

The work is split by semantic dependency rather than by host/runtime.

## Phase A — exact frontend substrate

Deliverables:

- lexer support for every V1 terminal (`module`, `import`, `export`, `capability`, `record`, `enum`, `fn`, `behavior`, `use`, `match`, `for`, `in`, `observation`, `effect`, `Some`, `None`, `Ok`, `Err`, `->`, `=>`, `..`, `::`, `<`, `>`);
- versioned AST able to represent both source-unit kinds and every V1 declaration/type/expression/statement/pattern;
- parser implementing the exact EBNF with no prose-only grammar branches;
- source-version gate preserving V0.2 behavior;
- syntax negative corpus for every new production and delimiter ambiguity;
- exact source spans for all nodes and diagnostics.

Exit gate: every EBNF production has at least one positive parser vector and at least one relevant malformed counterfactual.

## Phase B — deterministic linker and name system

Deliverables:

- explicit source-set linker API;
- exactly-one-root check;
- module-id index independent of paths;
- missing/duplicate import rejection;
- import-cycle detection with deterministic cycle witness;
- export/private enforcement;
- namespace-aware resolution;
- ambiguity detection;
- direct-import-only visibility;
- canonical semantic ids;
- deterministic module/declaration ordering;
- linked-program schema validation;
- source-order/path-order counterfactual campaign.

Exit gate: permuting source-unit input order and relocating all files preserves linked canonical bytes and semantic hash.

## Phase C — V1 type system and static semantics

Deliverables:

- recursive `TypeRef` parser/normalizer for `Option`/`Result`;
- nominal record/enum identity;
- acyclic record dependency validation;
- `Unit` placement restrictions;
- exact assignment compatibility and `Int -> Rat` widening;
- constructor validation;
- record field access typing;
- enum variant typing;
- `Option`/`Result` constructor contextual typing;
- operator typing for new value kinds;
- lexical block scopes without shadowing;
- deterministic diagnostic codes.

Exit gate: positive/negative static semantics corpus covers every type rule and every forbidden `Unit`/recursion/shadowing case.

## Phase D — purity, constants and effect inference

Deliverables:

- pure-function symbol table;
- user-function call graph;
- recursion/cycle rejection;
- capability-in-pure-function rejection;
- deterministic constant evaluator;
- state initializer constant proof;
- capability declaration merge/compatibility rules;
- per-handler and per-entity capability requirement summaries.

Exit gate: function declaration order does not affect canonical output; any recursive or effectful pure-function counterfactual fails closed.

## Phase E — behaviors, bounded control flow and match

Deliverables:

- behavior dependency graph;
- deterministic depth-first expansion in explicit use order;
- duplicate/diamond inclusion rejection;
- state and event-signature conflict detection;
- behavior-return rejection;
- nested lexical scopes;
- static half-open `for` validation;
- expansion-budget accounting;
- exhaustive enum/Option/Result match checking;
- arm binding types/scopes.

Exit gate: behavior expansion and loop unrolling have deterministic witnesses; every missing/duplicate/impossible match arm is rejected.

## Phase F — IR-V2-preserving V1 lowering

Implement only features proven erasable before runtime IR:

- modules/imports/export erased after resolution;
- pure functions inlined after acyclic purity validation;
- static `for` unrolled after budgets;
- behaviors expanded before handler lowering;
- primitive-only custom capability declarations lowered into the typed capability catalog.

The existing IR V2 validator remains authoritative after lowering.

Exit gate: V1 programs using only erasable features execute with byte-identical Python/JavaScript/C# receipts and do not change any V0.2 receipt.

## Phase G — freeze IR V3 for non-erasable values

Do not implement host-specific shortcuts.

Freeze:

- runtime type-id representation;
- canonical record values;
- canonical enum values;
- `Option` and `Result` values;
- equality semantics;
- field-load instruction(s);
- constructor instruction(s) or equivalent canonical value operations;
- match/control-flow lowering;
- stack/local verifier rules;
- schema changes;
- canonical JSON representation;
- checkpoint representation;
- signed-update compatibility boundary.

Exit gate: IR V3 schema + operational semantics + typed flow verifier are internally closed before runtime implementation.

## Phase H — runtime parity

Implement IR V3 in this order:

1. Python reference runtime;
2. JavaScript ES2022 runtime;
3. C# Core runtime;
4. Unity Core mirror;
5. Browser-WASM AOT;
6. WASI/Wasmtime AOT.

Each host must reproduce canonical receipts byte-for-byte before the next promotion step.

## Phase I — V1 conformance closure

Required campaigns:

- complete positive feature matrix;
- complete negative static boundary matrix;
- deterministic source-order permutation campaign;
- semantic-hash counterfactual campaign;
- cross-runtime receipt parity;
- checkpoint/restart with V1 values;
- signed update across V1 semantic hashes;
- V0.2 exact regression replay;
- Browser-WASM and WASI AOT no-regression;
- clean-commit content identity certification.

## Non-goals for V1.0

Do not open async, unbounded loops, recursion, inheritance, reflection, runtime codegen, user generics, maps, threads, exceptions-as-control-flow or network package resolution while V1 is being closed. Those change the proof surface and must be separate language revisions.

## Engineering rule

A feature is not marked complete because it parses. Completion requires:

`syntax -> name resolution -> typing -> static safety -> canonical link form -> lowering profile -> runtime semantics when required -> positive vectors -> negative counterfactuals -> cross-host evidence`.
