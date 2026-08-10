# TEV Script Discovery / Realization Duality V0

Status: **research architecture contract**.

This document does not assert that discovery and realization are mathematical inverses, nor that LNU is an established universal physical law. It defines a falsifiable common contract shape for testing the hypothesis that scientific discovery, structural abstraction and computational realization share a useful regime architecture.

## 1. Two directions

The upward direction is epistemic:

```text
world / experience
  -> observations
  -> admissible-history hypotheses
  -> causal/equivalence structure
  -> invariants
  -> candidate law / Transformation
```

The downward direction is constructive:

```text
candidate law / Transformation
  -> regime constraints
  -> candidate realizations
  -> admissibility/equivalence/invariant preservation
  -> admitted realization
  -> intervention / execution
  -> world / observed history
```

The same project may therefore close the loop:

```text
WORLD
  -> DISCOVER
  -> LAW / TRANSFORMATION
  -> REALIZE
  -> ACTION
  -> WORLD
```

## 2. Not an inverse law

R0 explicitly rejects the unjustified claim:

```text
Discover(Realize(L)) = L
```

in general.

Observation may be partial, interventions may be insufficiently identifying, realization may be approximate, the discovery algorithm may be incomplete, regimes may be observationally equivalent, and several theories may fit the same finite evidence.

Instead TEV represents a **round-trip consistency claim**:

```text
L
 -> admitted R
 -> observed history H
 -> discovery claim L'
 -> governed comparison between L and L'
```

and asks whether the comparison is supported under explicit evidence/scope assumptions.

## 3. Common regime shape

The research hypothesis is that both directions can often be represented by:

```text
possibility space
  -> hard constraints
  -> admissible subspace
  -> governed equivalence
  -> quotient / structural class
  -> invariants
```

In discovery, representatives are histories/models/formulations.

In realization, representatives are implementations/execution plans/hardware mappings.

The spaces are not assumed to be identical. Only the contract shape is shared.

## 4. Law as a structural semantic claim

A law is not identified with source text or a single equation.

A StructuralLawClaim binds:

```text
RegimeContract
Transformation semantic identity
validity boundary
assumptions
falsifier profile
evidence policy
```

The `law_semantic_hash` excludes display name and provenance metadata.

Two differently named/formatted claims that reference the same canonical structural objects therefore have the same semantic identity.

When two formulations use different concrete representations, equality of hashes is not assumed. A separate `LawEquivalenceClaim` states that their structural semantic classes are equivalent under an explicit relation/scope, and evidence must support that claim.

## 5. Syntax-independent identity does not mean automatic isomorphism

Canonical hashing alone cannot discover that two differently encoded structures are isomorphic.

For example:

```text
operation a (*) b
operation x (diamond) y
```

may encode the same abstract algebra while having different concrete hashes.

The system must discover/propose an isomorphism/equivalence witness and validate it.

Thus:

```text
same canonical structure -> same semantic hash

different concrete structures
  + proved governed equivalence
  -> same equivalence class
```

The second case is a theorem/evidence problem, not a hash-normalization trick.

## 6. DiscoveryClaim

A DiscoveryClaim binds:

```text
experience-space hash
observation-set hash
intervention-set hash
candidate law semantic hash
discovery context hash
validity-boundary hash
assumption hashes
```

It means:

> under this context and these assumptions, this candidate structural law is proposed as explaining/governing the supplied experience within the declared boundary.

It is a claim, not truth.

Evidence supporting/falsifying the claim is separate.

## 7. Law realization as hypothesis

A new Realization can itself be treated epistemically as a hypothesis:

```text
H_R:
"candidate R realizes Transformation T under Regime G"
```

The normal realization admission receipt provides pre-execution evidence.

Execution then provides additional observations/traces that may support, weaken or falsify the hypothesis.

Compilation/synthesis can therefore participate in the same operational cycle:

```text
hypothesis
 -> construct/intervene
 -> observe
 -> compare invariants
 -> update evidence
```

This does not make testing equivalent to proof; evidence method/scope remain explicit.

## 8. Realization as experiment

For an adaptive compiler/realizer, generating R is an intervention in a computational regime.

Measurements may reveal:

```text
semantic divergence
resource-model error
unstated machine assumption
approximation violation
causal/effect mismatch
performance improvement
```

A measured improvement changes the cost model, not the Transformation semantic identity.

A semantic counterexample changes the admissibility/evidence state of R.

## 9. Discovery as semantic compression

The reverse direction can be viewed as structural compression:

```text
large experience/history set O
  -> candidate compact structural claim L
```

A useful law explains/predicts/intervenes over many admissible representatives using less structural description than enumerating them individually.

R0 does not hard-code Kolmogorov complexity, MDL or one compression metric as the definition of law. Such criteria can become explicit policy/evidence dimensions in H experiments.

## 10. Equivalence classes of laws

Let `LawSemantic(L)` identify the canonical structural claim.

A governed LawEquivalenceClaim defines:

```text
L1 ~ L2
```

under:

```text
equivalence relation hash
semantic scope hash
assumption hashes
```

The claim is symmetric in its two law semantic hashes.

Evidence may establish an isomorphism, bisimulation, observational equivalence, logical equivalence, canonical semantic equality or another explicitly defined relation.

TEV Script does not assume one universal law-equivalence relation.

## 11. Domain of validity

Every nontrivial law claim must be able to express a validity boundary.

The architecture rejects the implicit escalation:

```text
L holds in observed regime R
therefore L holds universally
```

A law claim binds:

```text
validity boundary
assumptions
falsifier profile
```

so counterexamples can distinguish:

```text
law false inside claimed regime
```

from:

```text
observation outside claimed regime
```

when sufficient evidence exists.

## 12. Falsifier profile

A law claim may reference a canonical falsifier profile specifying classes of observations/interventions that would contradict the governed claim.

The profile does not guarantee that those experiments are physically available or computationally decidable.

It makes explicit what evidence would count against the claim within the declared formal regime.

## 13. Round-trip consistency

A DiscoveryRealizationCycle binds:

```text
source law semantic hash
admitted realization receipt hash
executed/observed history hash
rediscovery claim hash
rediscovered law semantic hash
optional LawEquivalenceClaim hash
```

Cycle comparison has three broad outcomes:

```text
PASS
  source and rediscovered law are canonically identical,
  or a governed equivalence claim is adequately evidenced

PROOF_REQUIRED
  consistency is plausible/claimed but equivalence evidence is incomplete

REJECT
  evidence falsifies the comparison or the cycle bindings contradict
```

A REJECT does not by itself localize blame to discovery or realization. Causal diagnosis requires the associated evidence/Residual graph.

## 14. Generative direction

A stronger understanding test asks the system to synthesize a model/world compatible with a law:

```text
LAW
 -> synthesis
 -> MODEL / WORLD
```

with a governed ModelCompatibilityClaim:

```text
MODEL satisfies LAW within Regime/Boundary
```

This is another realization problem and therefore reuses Realization Semantics rather than creating a separate magical `generate_world` primitive.

## 15. Operational understanding

R0 treats “understanding” as a research benchmark concept, not a primitive status.

A benchmark may independently test capabilities such as:

```text
recognize instances
predict held-out instances
recover invariants
produce counterfactuals
choose informative interventions
transfer across isomorphic encodings
generate compatible models
construct admitted realizations
identify domain-of-validity boundaries
produce falsifiers/counterexamples
```

Reporting these as a capability vector is safer than assuming every system progresses along one total scalar intelligence ladder.

A contiguous U0..Un level may be derived for convenience only when explicit prerequisite rules are declared.

## 16. Concepts as invariants — research hypothesis

The proposal:

> a concept may be represented by structure invariant under a governed family of admissible transformations

is retained as a falsifiable research hypothesis.

Examples might include object identity under viewpoint/illumination changes or algebraic structure under renaming/isomorphism.

R0 does not claim all concepts are exhaustively definable as group invariants. Relevant transformation families may form categories, groupoids, simulations, partial maps or other structures.

H should test where the hypothesis succeeds and where richer structure is required.

## 17. Perception, mathematics and programs

The same contract shape may appear in:

```text
perception:
  observations -> viewpoint equivalence -> object invariant

mathematics:
  presentations -> isomorphism/equivalence -> abstract structure

programs:
  implementations -> semantic equivalence -> Transformation invariant

science:
  histories -> causal/equivalence quotient -> regime law
```

The repeated shape is evidence for a reusable abstraction only if held-out domains can use the same core without domain-specific hidden code.

## 18. H as falsification laboratory

The strongest next test is not to add more named theories to TEV Script.

H should receive opaque/generated domains and test whether a generic pipeline can infer/use:

```text
constraints
equivalence candidates
invariants
regime boundary
transfer map
```

without domain labels or hard-coded theorem names.

Candidate families include:

```text
finite algebra
finite automata / transition systems
cellular/dynamical systems
geometric incidence worlds
causal intervention worlds
stochastic finite processes
distributed protocols
program semantics/generated interpreters
unknown procedurally generated worlds
```

## 19. Falsification criteria for the common architecture

The hypothesis `constraint -> quotient/equivalence -> invariant` is weakened or rejected if held-out tests show one or more of the following persistently:

1. useful laws require domain-specific primitives in the core;
2. no representation-independent equivalence can be recovered without leaking names;
3. invariants do not support prediction/intervention beyond memorized examples;
4. transfer across isomorphic/behaviorally equivalent encodings fails;
5. generated models satisfying inferred laws do not reproduce held-out regime behavior;
6. boundary-of-validity detection systematically fails;
7. realization preservation requires semantics not expressible through the generic regime contract;
8. the quotient discards causal/effect information required for correct intervention;
9. different domains require fundamentally incompatible notions with no useful common abstraction beyond vacuous “constraints exist”.

A negative result is a valid R0/H result and should refine or reject the unification claim.

## 20. Anti-cheating requirements

Held-out H/LNU campaigns should require:

```text
opaque symbols
random symbol permutations
representation changes
isomorphic recodings
negative/counterfactual worlds
unseen domain family instances
no domain-name branches in acquisition core
no expected-law strings in core
no benchmark-id conditionals
```

A discovered equivalence/invariant must be evidenced from supplied structure/interaction, not benchmark metadata.

## 21. Bidirectional benchmark closure

For each held-out family, a strong campaign should test both:

```text
DISCOVERY:
world/observations -> law claim

REALIZATION:
law claim -> compatible model/implementation
```

and then:

```text
ROUND TRIP:
law -> realization -> observations -> rediscovery -> governed comparison
```

The round trip is not required to recover identical syntax.

It should recover the same governed structural class within declared scope when the experiment is identifying enough.

## 22. Self-science and recursive improvement

IA-TEV may be studied as another governed system:

```text
cognitive traces
 -> hypothesis about strategy/regime
 -> controlled intervention
 -> measurement
 -> candidate cognitive law
 -> improved Transformation
 -> independent verification
 -> governed adoption
```

This is a realistic route to recursive improvement only if generator and verifier authority remain separated.

The agent cannot make its own candidate correct merely by asserting a favorable law/evidence claim.

## 23. No self-certification

Mandatory boundary:

```text
Generator
 -> candidate
 -> independent verifier/evidence boundary
 -> admission policy
```

For verifier/policy changes, a higher authority stratum is required.

A candidate cannot rewrite the verifier/policy that validates the same transition and then use that rewritten authority as the sole evidence for admission.

## 24. Relationship to CUOFC / LNU / TIRV / TEV / IA-TEV

One useful separation is:

```text
CUOFC
  structural/ontological substrate

LNU
  hypothesis/principle of regime formation and invariance

TIRV
  formal restriction/causality/quotient/invariant machinery

TEV
  active epistemic cycle: observe/hypothesize/intervene/falsify

TEV Script
  exact executable/canonical representation and realization boundary

IA-TEV
  autonomous consumer coordinating discovery, reasoning, synthesis and action
```

Operational dependencies may form feedback loops, but semantic authority remains explicit rather than circular.

## 25. Central scientific question

The project should treat the following as a falsifiable research question:

> Is the architecture `possibilities -> restrictions -> admissible structure -> governed equivalence/quotient -> invariants` sufficiently expressive to discover, compare and realize useful structures across radically different held-out domains without domain-specific knowledge in the core?

R0 does not answer “yes”. It constructs the contracts required to test the question rigorously.