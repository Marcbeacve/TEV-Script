# TEV Script Standalone Semantic Authority V0

Status: **post-V1 experimental, additive, non-normative for TEV Script V1**.

## 1. Authority boundary

TEV Script owns its executable semantic authority. A third-party implementation must be able to implement and validate TEV Script from TEV-owned language, semantic-calculus, IR, ABI and conformance specifications without importing or installing any external metatheory or prover implementation.

No external metatheory/prover is required for parsing, checking, compilation, runtime execution, portable conformance, the Semantic Apply Calculus, the Semantic Frontier Closure, V1 `CERTIFY_FULL`, Python `CERTIFY_FULL`, or performance-promotion eligibility.

External formal systems remain useful as **optional independent evidence providers**. They do not define TEV Script semantics and do not receive transitive write, promotion, truth or language authority.

## 2. Provider-neutral oracle contract

Optimization evidence uses a TEV-owned process boundary:

```text
TEV Script candidate
      |
      +-- local reference finite oracle (default, self-contained)
      |
      +-- optional external oracle adapter
               |
               +--> provider-specific implementation
```

Every provider must emit `TEV_SCRIPT_V1_OPTIMIZER_ORACLE_RECEIPT_V1`. The contract records provider identity and evidence scope and explicitly forbids the finite oracle from claiming universal integer equivalence, runtime-implementation equivalence, write authority or promotion authority.

The default provider lives in this repository and exhaustively compares the closed optimizer transformation families over declared finite carriers with negative controls. Existing optimized-runtime/host regression tests remain the independent implementation-equivalence obligation.

## 3. No ambient discovery

Required TEV Script surfaces must not probe machine-specific paths for external semantic authorities. An optional provider is selected explicitly by its adapter executable/script. Absence of external providers cannot change TEV Script language semantics.

## 4. Normative separation

The executable authority chain is:

```text
TEV-owned specification
       -> TEV Semantic Calculus
       -> TEV Semantic IR / runtime contract
       -> TEVScript implementations
```

External theories may motivate or analyze this chain, but are not runtime/build dependencies. Correspondence documents with external theories are research artifacts and are non-normative unless a future TEV language version explicitly adopts a result through its own governed specification process.

## 5. Adapter rule

An adapter may know the name, layout or API of one external prover. Required language/runtime/certification code must not. Provider-specific adapters may preserve legacy provider receipts while additionally emitting the provider-neutral TEV optimizer-oracle receipt.

## 6. Research-correspondence boundary

A non-normative research document may name an external theory and state a translation or comparison. Such a document must not be imported by runtime/build/certification code, must not define TEV language meaning by reference, and must not create a version or package dependency. The decoupling gate therefore constrains TEV authority surfaces, not scholarly provenance.

## 7. Closure gates

V0 requires:

```text
NO_NAMED_EXTERNAL_METATHEORY_AUTHORITY_DEPENDENCY=PASS
NO_EXTERNAL_METATHEORY_RUNTIME_DEPENDENCY=PASS
NO_EXTERNAL_METATHEORY_BUILD_DEPENDENCY=PASS
NO_EXTERNAL_METATHEORY_CERTIFICATION_DEPENDENCY=PASS
NO_DEFAULT_EXTERNAL_PROVER_PATHS=PASS
STANDALONE_OPTIMIZER_ORACLE=PASS
NONNORMATIVE_RESEARCH_CORRESPONDENCE_ALLOWED=PASS
SEMANTIC_CALCULUS_NON_REGRESSION=PASS
SEMANTIC_FRONTIER_NON_REGRESSION=PASS
```

## 8. Boundary

V0 does not claim that external theories are irrelevant or that TEV Script invented their mathematics. It claims only an architectural authority boundary: TEV Script can define, execute and certify its current semantics without a transitive dependency on an external theory repository.

`LANGUAGE_STABLE=NO`. This document grants no merge, release or stable-promotion authority.
