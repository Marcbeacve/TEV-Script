# TEV Script Semantic Frontier Closure V0

Status: **post-V1 experimental, additive, non-normative for TEV Script V1**.

This closure defines exact supported fragments and explicit proof boundaries for the five previously open Semantic Apply Calculus V0 frontiers. It adds no V1 syntax, runtime opcode, kernel sort, or host authority.

## 1. Closure rule

A frontier is closed when the supported fragment has an exact falsifiable judgment and every more general case fails closed as `PROOF_REQUIRED` unless a scope-bound proof from an explicitly trusted verifier is supplied.

This does **not** mean that undecidable mathematical problems have become decidable.

## 2. Paraconsistent inference and revision

Finite propositional inference uses four evidence values:

```text
NEITHER
TRUE_ONLY
FALSE_ONLY
BOTH
```

Negation, conjunction and disjunction use Belnap/Dunn-style support/refutation semantics.

`finite_entails` exhaustively searches all four-valued valuations up to an explicit bound and returns an explicit countermodel when entailment fails. Larger spaces return `PROOF_REQUIRED`.

Contradiction does not explode: support for `p` and `not p` does not by itself support an unrelated proposition `q`.

Belief revision is explicitly `RevisionPolicyV0`-bound. Source priority and knowledge-time preference are content-addressed by the policy. TEV does not claim one universal belief-revision policy.

## 3. Liveness and fairness

For finite transition systems, `finite_fair_eventually` is exact.

A maximal finite execution that reaches a non-goal deadlock violates eventuality. An infinite fair counterexample exists iff a reachable cyclic SCC avoiding the goal satisfies every non-empty declared justice set.

Empty justice sets are invalid rather than vacuously satisfied.

General/infinite liveness returns `PROOF_REQUIRED` unless a strong proof witness is accepted by an explicit verifier trust policy for the exact scope.

## 4. Actual causality

Causal claims are criterion-bound.

V0 implements the exact finite criterion:

```text
TEV_BUT_FOR_MINIMAL_V0
```

over finite acyclic Boolean structural causal models.

The model, exogenous context, candidate cause assignment, outcome, counterfactual intervention and minimality are explicit.

The built-in fragment rejects:

- empty causes;
- causes that are not endogenous variables;
- outcomes that are not endogenous variables;
- trivial self-causation;
- non-actual causes/outcomes;
- candidates that fail the but-for test;
- non-minimal multi-variable causes.

Richer actual-causality criteria remain `PROOF_REQUIRED` unless a scope-bound proof is accepted by a trusted verifier.

Temporal precedence alone is never a causal proof.

## 5. Trace-level computational universality

A deterministic two-counter machine is embedded one machine step at a time through:

```text
SemanticFieldV0
+
rule_field
+
apply_rule
```

Each operational quantum is bounded and terminates. Long-running computation is represented by an unbounded trace of explicit resumptions.

The universality judgment is deliberately relative. It becomes `PASS_RELATIVE` only when:

1. the TEV step embedding is exact for the required proof scope; and
2. a trusted scope-bound witness establishes the source theorem that the chosen two-counter-machine model is universal.

No single Reaction or quantum is claimed to be unbounded.

## 6. Composition theorem

Semantic composition requires:

- a `law_hash` derived from the exact `DomainLawV0` mapping used by the proof;
- operation non-interference;
- effect/resource commutativity;
- applicability in both orders;
- dynamic diamond closure.

A static claim whose dynamic diamond fails yields `LAW_VIOLATION`.

Observations are not treated as freely commuting without a realized observation witness.

Physical commit composition additionally requires a trusted scope-bound proof of external commit serializability. Semantic commutativity is never silently promoted to physical-world commutativity.

Finite rule families are exhaustively permutation-checked up to an explicit bound. Larger families return `PROOF_REQUIRED` unless a trusted family-serializability witness is supplied.

## 7. Proof boundary

`ProofBoundaryWitnessV0` is not self-authenticating.

It binds:

```text
proof_hash
verifier_hash
scope_hash
method
status
```

Acceptance additionally requires a `VerifierTrustPolicyV0` that explicitly trusts the verifier hash.

Only active witnesses using:

```text
proved
attested
exhaustive
```

are strong.

`sampled` and `assumed` never certify a universal claim.

## 8. Closure result

The five frontiers are closed at the semantic-contract level as follows:

| Frontier | Exact built-in fragment | General boundary |
|---|---|---|
| Paraconsistency | finite propositional four-valued entailment | `PROOF_REQUIRED` beyond configured exhaustive bound |
| Belief revision | explicit `RevisionPolicyV0` | no universal revision policy claimed |
| Liveness/fairness | finite transition systems + state justice | trusted scope-bound proof |
| Actual causality | finite Boolean minimal but-for | criterion-bound trusted proof |
| Universality | literal two-counter `Field+Apply` step embedding | relative to trusted source universality theorem |
| Composition | conditional semantic diamond + bounded family permutations | trusted proof for larger/physical scopes |

No new primitive is introduced into the Semantic Apply Calculus V0.
