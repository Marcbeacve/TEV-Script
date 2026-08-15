# TEVScript_max — Master Design

Date: 2026-08-15

## Objective

Evolve TEV-Script from a stable bounded deterministic language into a verifiable execution substrate that can serve IA-TEV as a governed execution layer for plans, capabilities, tools, learned organs, durable state, and eventually portions of self-evolution.

The stable TEV-Script V2.0.0 release remains immutable authority:

```text
BASE_COMMIT=2bdb047dcad41f9d112219bd65925c25668c02e0
BASE_TREE=aa00bf02f6d7cca7cb5a9a21daf18370ba3dd2b8
LANGUAGE_VERSION=2.0.0
STABLE_ADMISSION_RECEIPT_SHA256=4235895f6229e168ff315c41624c23c205692046b74e030f6fd3fc8ca40adfe6
```

TEVScript_max is a new evolution track. It must never silently rewrite V2 stable semantics or inherit V2 stable admission for new semantics.

## Governing idea

The platform should maximize expressivity and portability without granting ambient authority or unbounded execution.

The governing composition is:

```text
TOTAL CORE
+ TYPE/PROOF LAYER
+ CONTENT-ADDRESSED MODULES
+ PROOF-CARRYING PROGRAM IR
+ PORTABLE / NATIVE / DISTRIBUTED RUNTIMES
+ UNIVERSAL CAPABILITY KERNEL
+ RECEIPTS
+ DURABLE STATE
+ FINITE-EPOCH SUPERVISION
```

Open-ended behavior is expressed as an unbounded sequence of individually bounded, verified transitions:

```text
S0 --P0--> S1 --P1--> S2 --P2--> ...
```

Every Pi is finite, content-addressed, independently admitted, capability-bounded, and replayable. No `while true`, uncontracted recursion, unrestricted code generation, or ambient FFI is introduced.

## Architecture principles

1. TEV-Script remains semantic authority. External provers may verify claims but do not redefine language semantics.
2. Production runtimes consume admitted IR/artifacts, never source directly.
3. All host authority crosses explicit typed capabilities.
4. Every physical effect follows `request -> plan -> grant -> commit -> receipt`.
5. Exact integer/rational semantics remain exact until a capability explicitly converts them.
6. Missing authority, malformed artifacts, hash mismatch, invalid proof, exhausted resource budgets, or unsupported secure primitives fail closed.
7. Native/WASM/distributed execution is observationally equivalent to the canonical IR semantics.
8. Optimizations and AOT code remain subordinate to `program_ir_hash` identity.
9. Self-modification means proposal -> build -> proof/tests -> content-addressed artifact -> explicit admission -> hot swap; runtime memory mutation is not authority.

## Program decomposition

The roadmap is deliberately split into independently certifiable subprojects.

### R1 — Total Core

Goal: substantially generalize total computation without allowing arbitrary nontermination.

Features:

- user-defined algebraic data types / sum types;
- generic recursive ADTs;
- exhaustive pattern matching over user ADTs;
- structural recursion certificates;
- lexicographic measures over finite tuples;
- well-founded measure interface with a closed initial set of proof rules;
- multiple recursive call sites only when the termination checker proves every call decreases;
- optional mutual recursion only after SCC-level termination checking exists;
- higher-order source surface compiled by closure conversion + defunctionalization into a closed first-order IR;
- no runtime closures, reflection, or arbitrary heap object identity.

R1 is the first priority because it expands what IA-TEV can express while retaining totality.

### R2 — Proof-Carrying IR

Goal: make compiled artifacts carry compact machine-checkable evidence.

Initial proof obligations:

- type safety / type-table closure;
- termination contract;
- static step bound;
- memory/stack/task/effect upper-bound vector;
- purity / capability set;
- source-semantic-hash -> IR binding;
- canonical artifact integrity.

A small verifier kernel checks certificates before execution. Proof artifacts are additive evidence; runtimes still fail closed if evidence is malformed or unsupported.

### R3 — Metatheory

Mechanize the core semantics and prove preservation/progress/termination/determinism/capability non-escalation for the admitted profile. Lean or TEVProver may be external proof engines; generated proof receipts bind exact TEV-Script semantic artifacts.

### R4 — Independent Runtime + WASM / Native

Build an implementation independent of Python, preferably Rust first, then WASM. Require parity on result, state, transcript, and canonical receipt bytes. Add AOT lowering from admitted IR to SSA/WASM/native with a binding receipt to `program_ir_hash`.

### R5 — Universal Capability ABI

Generalize capability providers without ambient authority. Families may include network/HTTP, database, processes, GPU, time, randomness, sensors, Unity, model inference, and storage. Each capability has typed request/response schemas, explicit authority lifetime, deterministic transcript semantics where applicable, and effect commitment receipts.

### R6 — Checkpoint / Replay / Epoch Runtime

Add Program IR checkpoint artifacts binding program hash, durable state, transcripts, pending intents, ledger head, resource counters, and epoch identity. A supervisor may admit the next finite epoch. This is the main open-ended execution mechanism for IA-TEV.

### R7 — Deterministic Distribution

Content-address pure/task DAG nodes, schedule them on heterogeneous workers, gather task receipts, and perform deterministic joins independent of physical execution order. Add communication and remote-resource bounds to the cost vector.

### R8 — Self-Hosting

Port lexer/parser/type checker/canonicalizer and compiler stages progressively into TEV-Script. Python becomes bootstrap/reference implementation rather than privileged semantics.

## Versioning

V2.0.0 remains stable and unchanged. TEVScript_max development uses explicit candidate profiles and does not claim a release version until the first semantic frontier is closed. Any new stable language version requires its own certification and Stable Admission chain.

## R1 Total Core detailed design

### User ADTs

Source concept:

```text
adt Tree<T> {
    Leaf(T),
    Node(Tree<T>, Tree<T>)
}
```

The exact syntax may follow the existing TEV lexical profile, but semantic requirements are fixed:

- nominal type identity;
- deterministic constructor order in canonical form;
- unique variant names;
- each variant carries zero or more typed fields;
- zero-field variants are constructor tags and do not store `Unit`;
- recursive occurrences are allowed only through named ADT references;
- monomorphization is finite and compile-time bounded;
- descriptors are content-addressed and closed before runtime.

Runtime representation is the existing variant/value model generalized from built-in `Option/Result` to nominal user ADTs.

### Exhaustive match

`match` over a user ADT must cover every declared variant exactly once. Variant payload bindings are statically typed. Match exhaustiveness and duplicate arms are compile-time properties.

### Termination contract model

Replace the current single `decreases Int` special case with a general contract object:

```text
TerminationMeasure =
    IntDecrease(parameter)
  | StructuralSubterm(parameter, path)
  | Lexicographic(measure1, measure2, ...)
```

Initial R1 admits only measures whose decrease can be proven syntactically and compositionally. A future proof-carrying R2 may admit more general externally constructed well-founded proofs.

Every recursive call site must carry a compiler-derived decrease witness. The compiler rejects unresolved or incomparable recursive calls before IR emission.

### Recursive call graph

R1 first closes direct self recursion with multiple proven call sites. Mutual recursion is gated behind an SCC termination analyzer and is not required for the first R1 admission. This prevents scope explosion while still enabling structural algorithms such as tree folds, list-like ADT recursion, divide-and-conquer over structurally smaller arguments, and lexicographic recursion.

### Higher-order source surface

Higher-order functions are allowed only when the compiler can eliminate them before runtime:

```text
source closures / function values
    -> closure conversion
    -> finite environment record
    -> defunctionalized function-tag ADT
    -> first-order dispatch
    -> closed IR
```

No runtime source compilation, dynamic function loading, reflection, or arbitrary executable pointer enters the runtime ABI.

### Resource bounds

R1 preserves finite execution. Each admitted program derives a preliminary cost vector:

```text
C(P) = (steps, stack, value_nesting, collection_capacity, tasks)
```

R2/R6 later extend it with memory bytes, IO, effects, communication, and durable-state bounds.

## R1 fail-closed obligations

The compiler/runtime must reject:

- recursive ADT instantiation cycles that exceed monomorphization bounds;
- non-exhaustive or duplicate matches;
- recursive calls without a proven decrease;
- lexicographic measures with unresolved components;
- structural recursion on a value not proven to be a strict subterm;
- closure environments containing non-storable or ambient host references;
- defunctionalization sets that cannot be closed at build time;
- runtime artifacts whose ADT/type/termination hashes do not match the compiled contract.

## R1 compatibility gate

All existing V2 programs must retain their V2 behavior on the V2 compiler/runtime. The new candidate frontend may accept a strict superset, but cannot retroactively redefine V2 stable artifacts.

Required R1 evidence:

```text
V2_STABLE_BASE_UNCHANGED=PASS
V2_EXISTING_REGRESSION=PASS
USER_ADT=PASS
GENERIC_RECURSIVE_ADT=PASS
EXHAUSTIVE_MATCH=PASS
STRUCTURAL_RECURSION=PASS
LEXICOGRAPHIC_TERMINATION=PASS
UNPROVEN_RECURSION=FAIL_CLOSED
HIGHER_ORDER_DEFUNCTIONALIZATION=PASS
CLOSED_RUNTIME_IR=PASS
DETERMINISTIC_REPLAY=PASS
NO_AMBIENT_AUTHORITY=PASS
```

## Relationship to IA-TEV

R1 immediately increases the class of learned/generated algorithms that IA-TEV can safely synthesize and execute. R5/R6 later make TEV-Script the capability and durable-epoch substrate. The final target is that IA-TEV may propose source/IR/capabilities, while TEV-Script supplies bounded semantics, proofs, execution, state transition, and receipts.
