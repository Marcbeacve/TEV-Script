# TEV Script V1 compiler/runtime portability boundary decision

Status: **candidate architecture decision**
Date: 2026-08-08

## Decision

The normative portable handoff between TEV Script source semantics and host execution is:

```text
TEV Script V1 source set
  -> reference frontend/link/static semantics
  -> TEV_SCRIPT_LINKED_PROGRAM_V1
  -> target lowering
     -> TEV_SCRIPT_PROGRAM_IR_V2  (erasable profile)
     -> TEV_SCRIPT_PROGRAM_IR_V3  (full algebraic profile)
  -> independently validating host runtimes
```

V1 portability does **not** require three separately maintained source compilers merely because three runtime hosts exist.

The repository SHALL maintain one normative reference compiler pipeline whose output is the canonical `TEV_SCRIPT_LINKED_PROGRAM_V1` artifact. JavaScript, C#, Rust, C++, browser, WASI or other hosts may consume validated target IR without reimplementing source parsing/linking.

Independent source compilers in other implementation languages remain desirable conformance implementations, but they are optional secondary implementations rather than a prerequisite for the semantic completeness of V1.

## Why

### 1. Semantic identity already exists before runtime IR

`TEV_SCRIPT_LINKED_PROGRAM_V1` removes:

- source paths;
- filesystem order;
- import discovery order;
- source-local alpha names;
- non-semantic declaration ordering;
- syntactic differences in constant initializers.

It resolves nominal ids, visibility, types, functions, behavior composition, effects and constant state before a target runtime is selected.

Duplicating three complete source compilers would therefore duplicate the most semantically sensitive layer after a canonical boundary already exists.

### 2. Multi-host independence belongs at validation/execution

The strongest cross-host property is that independent host runtimes:

- validate the same IR contract;
- reject the same negative corpus;
- execute the same typed abstract machine;
- produce byte-identical canonical receipts.

That property is already falsifiable without requiring each host to parse source syntax.

### 3. DRY and proof-surface reduction

Three independently evolving parsers/linkers/type checkers create three semantic-drift surfaces. Requiring all three for every language feature multiplies maintenance and proof obligations without increasing the expressiveness of TEV Script.

One reference compiler plus independent IR validators/runtimes gives a smaller trusted semantic translation boundary and a larger independently checked execution boundary.

### 4. Host neutrality is preserved

The reference compiler is not a Python-runtime dependency. It is a build-time implementation of a normative language specification. Its semantic output is canonical data with published schemas and hashes.

A production host may receive only the linked artifact or target IR and never embed Python.

## Required stable-V1 authorities

Stable V1 SHALL require:

1. source grammar/lexical/static semantics closed;
2. deterministic reference compiler source→linked program closed;
3. `TEV_SCRIPT_LINKED_PROGRAM_V1` schema/canonicalization closed;
4. target lowering receipts bind linked semantic hash to target IR hash;
5. at least the required portable host runtimes independently validate target IR;
6. shared negative corpus parity across those runtimes;
7. byte-identical execution receipts across the required host runtimes;
8. checkpoint/restart parity where checkpointing is part of the runtime profile;
9. Browser-WASM/WASI parity for the production portable profile;
10. exact clean-commit certification and V0.2 regression preservation.

## Optional conforming source compilers

A JavaScript/C#/Rust/etc. source compiler MAY claim `TEV_SCRIPT_V1_SOURCE_COMPILER_CONFORMANT` only if it independently proves:

```text
source set
  -> identical TEV_SCRIPT_LINKED_PROGRAM_V1 canonical bytes
```

against the reference compiler over the positive/negative/permutation corpus.

Such a compiler must not create a new semantic dialect or alternative linked format.

## Counterfactuals

This decision is falsified if any of the following becomes true:

- the linked-program artifact omits information needed to reproduce target lowering;
- target runtimes must inspect original source paths/text to execute correctly;
- two valid target lowerers require incompatible interpretations of the same linked program;
- independent source compilers demonstrate that a material semantic ambiguity exists before linked canonicalization;
- compiler implementation-language behavior leaks into canonical linked bytes.

In those cases the fix is to strengthen the source/linked semantic contract first, not to rely on majority agreement among duplicated compilers.

## Current evidence

The current branch already demonstrates the intended separation for the shared V3 campaign:

```text
reference V1 semantic pipeline
  -> linked V1
  -> IR V3
  -> Python / JavaScript / C# validators+runtimes
  -> byte-identical conformance receipt
```

This evidence supports retaining the canonical linked-program boundary as the primary portability boundary while continuing Browser/WASI/checkpoint campaigns.
