# TEV Script Axiomatic System Layers V0

Status: **AXIOMATIC_CANDIDATE**  
Primitive semantic families: **Field + Transformation**  
Authority promotion: **forbidden until formal replay closes**

This document extends `TEV_SCRIPT_AXIOMATIC_SEMANTICS_V0.md` from the semantic
kernel to the complete TEV Script system boundary. These layers do not introduce
new semantic primitives. Every state-like object denotes a Field and every process,
compiler phase, verifier, admission, runtime transition or effectful operation denotes
a Transformation plus explicitly bound witnesses.

## L0 — Canonical representation and exact values

**L0.1 Canonical determinism.** The canonical serialization of a canonical object is
deterministic. Equal canonical objects produce equal canonical hashes. The converse
is deliberately **not** an axiom: SHA-256 is a binding mechanism, not mathematical
truth or semantic equality.

**L0.2 Exact values.** `Int` and `Rat` remain exact in language semantics. Rational
values are normalized numerator/denominator pairs and vectors are tuples of exact
rational components. Any lossy or host-native conversion is an explicit capability
boundary.

**L0.3 Round-trip preservation.** For every admitted typed value `v`, decoding its
canonical encoding yields the same semantic value. Malformed/non-normalized encodings
are rejected rather than repaired implicitly.

## L1 — Source, project, linking and compilation

**L1.1 Closed input.** Compilation depends only on the explicitly bound project/source,
language contract and declared compilation inputs; ambient host state is not semantic
input.

**L1.2 Deterministic compilation.** The same canonical compilation input produces the
same linked-program/IR semantic object and canonical identity.

**L1.3 Static rejection.** A malformed or statically invalid source/project cannot be
upgraded to a runnable IR by a later phase.

**L1.4 Source is not runtime authority.** Production runtimes consume validated IR,
not `.tevs` source. Parser/compiler implementations are implementations of language
authority, not a replacement authority.

## L2 — Lowering, IR and runtime transition

**L2.1 Preservation by lowering.** An admitted lowering binds the source/linked-program
identity to the produced IR identity and preserves the semantics claimed by that
lowering profile.

**L2.2 Runtime validation.** Runtime execution is defined only for validated IR under
the corresponding ABI/value-model contract.

**L2.3 Closed-transition determinism.** Holding validated IR, prior state, explicit
input, capability results and observations fixed, the semantic next state/trace is
unique up to the declared semantic equivalence. Apparent external nondeterminism must
enter through an explicit observation/capability result Field.

## L3 — Effects and capabilities

**L3.1 No implicit effect.** A physical/host effect can commit only through an explicit
capability whose scope admits that effect.

**L3.2 Missing law is not commutation.** Effects may be reordered/combined only when a
bound domain law proves the required relation. A missing law is a blocker, never an
implicit proof of commutativity.

**L3.3 No unresolved commit.** `REJECT`, `PROOF_REQUIRED`, missing capability, exhausted
budget or unresolved post-state cannot be promoted into a physical commit.

## L4 — Causal and semantic transformation

**L4.1 Causal authority remains explicit.** `.tev`/`.tevg` causal/general workflow
kernels remain their declared authorities. TEV Script may project/bridge them but does
not silently duplicate or replace them.

**L4.2 Semantic action.** The semantic core follows the Field/Transformation axioms
A0–A8, including governed composition, residual soundness and four-valued evidence.

**L4.3 Bridge direction is explicit.** A bridge imports the semantics it connects; it
does not create a circular authority inversion between causal and semantic layers.

## L5 — Evidence, proof and epistemic state

**L5.1 Evidence is not truth by identity.** Evidence/proof hashes bind artifacts and
scope; they do not make propositions true solely because the hash exists.

**L5.2 Proof scope.** A proof witness is admissible only when proof hash, verifier hash,
scope hash and trust policy match the claim being discharged.

**L5.3 Bounded honesty.** Exhaustive finite reasoning may return `PASS` only inside its
certified bound. Crossing the bound produces `PROOF_REQUIRED` rather than an estimate
masquerading as proof.

**L5.4 Paraconsistent object logic.** Conflicting support/refutation remains explicit as
`BOTH`; classical meta-logic used by Lean/Z3 does not collapse object-level evidence.

## L6 — Resources, measurements and cost

**L6.1 Resource non-negativity.** Resource bounds are non-negative exact rationals;
known upper bounds cannot be below lower bounds.

**L6.2 Catalog closure.** Resource vectors and ceilings are meaningful only relative to
the exact catalog they bind. Complete vectors cover the complete catalog.

**L6.3 Composition law.** Per dimension, sequential/parallel composition uses the
catalog-declared `SUM` or `MAX`. For a fixed catalog/mode these aggregations are
associative; the empty composition is the exact zero vector.

**L6.4 Unknown is not cheap.** An unknown upper resource bound cannot satisfy a finite
ceiling by assumption; it remains an explicit unresolved resource obligation.

**L6.5 Cost is not semantic identity.** Empirical measurements and cost models may
change admission/ranking without redefining realization semantics.

## L7 — Realization, selection and execution lifecycle

**L7.1 Admission before selection.** A selected realization is a bound candidate whose
admission is `PASS`; `PROOF_REQUIRED` and `REJECT` are not selections.

**L7.2 Honest ambiguity.** Multiple semantically distinct tied-best admissible
realizations yield `INDETERMINATE`, not a name/hash/backend/input-order tie-break.

**L7.3 Closed negative result.** `NO_ADMISSIBLE_REALIZATION` requires a closed candidate
set whose candidates are conclusively rejected. Any open admission keeps resolution
indeterminate.

**L7.4 Lifecycle binding.** Request, activation, execution, observation and grounded
discovery phases bind the identities of the states/artifacts they consume and produce;
a later phase cannot silently substitute an unbound predecessor.

## L8 — Receipts, artifacts and consumer boundary

**L8.1 Receipt integrity.** A receipt's canonical hash binds its exact body. Verification
also checks the semantic/system contract fields represented by that receipt; hash
matching alone is insufficient.

**L8.2 Exact distribution identity.** Post-V1 system consumers bind at least the exact
system API contract hash, distribution artifact SHA-256 and system integration receipt.
Package version alone is insufficient.

**L8.3 Standalone authority.** IA-TEV or another consumer may invoke TEV Script but does
not become TEV Script semantic authority. TEVProver, RepoTalk, Lean and Z3 certify
scoped obligations without gaining write/truth/promotion authority.

**L8.4 Candidate isolation.** This axiomatic candidate remains outside both historical
`CANONICAL_INDEX.json` and the post-V1 system canonical index until the required formal
receipts are replayed and bound.

## Formal allocation

- **Lean:** abstract algebraic/typed consequences of Field + Transformation,
  four-valued evidence, governed composition, residual and selection closure.
- **Z3 semantic:** selection safety, non-collapse and negative controls.
- **Z3 operational:** resource associativity, effect/capability fail-closed rules,
  unknown-resource honesty, exact receipt binding and closed-transition determinism.
- **TEVProver:** exact finite structural objects inside supported goal kinds only.
- **Static correspondence:** maps L0–L8/C0–C8 to the actual TEV Script surfaces and
  rejects premature authority binding.

A formal engine result is evidence for only the obligation and scope it actually
checks. No engine result by itself promotes this document to language/system authority.
