# TEV Script Semantic Residual V0

Status: **post-V1 experimental semantic authority; no V1 reinterpretation; `LANGUAGE_STABLE=NO`**.

## 1. Ontology

Residual is **not** a third primitive. TEV Semantic Calculus remains reducible to:

- `SemanticFieldV0` — represented semantic content;
- transformations/rules — relations that produce new fields.

A residual is a `SemanticFieldV0` using the profile `TEV_SCRIPT_SEMANTIC_RESIDUAL_V0`. `Residualize` is the transformation that derives that field relative to an explicit judgment.

For a field `F`, transformation `T`, context `Gamma`, laws `L`, and judgment `J`:

`F' = Apply(Gamma, L, F, T)`

`R = Residualize(F', J)`

The V0 closure law is judgment-scoped:

`Closed(R_J(F')) <=> no obstruction represented by J remains unresolved`.

It does **not** imply that `F'` equals an omniscient or complete world description.

## 2. Canonical residual field

The residual surface is exact and contains only:

- `tev.residual/8`
- `tev.residual.obstruction/7`

`tev.residual` binds:

1. profile;
2. `OPEN | CLOSED`;
3. residual domain;
4. judgment id;
5. judgment hash;
6. canonical judgment JSON;
7. source hash;
8. obstruction count.

Each obstruction binds a deterministic index, kind, subject, canonical expected value, canonical observed value, canonical detail map, and optional evidence hash.

The parser rejects hidden extra declarations/relations, malformed indexes/counts, status/count disagreement, invalid hashes, or judgment-hash drift.

## 3. Generic field requirement residual

`residualize_fields(observed, required, judgment_id, domain)` treats the body facts in `required` as the judgment-relevant requirements.

- exact required fact present -> no obstruction;
- same relation present with other arguments -> `value_mismatch`;
- relation absent -> `missing_fact`;
- observed facts outside the required judgment are irrelevant to closure.

This distinguishes a residual from a raw field delta. A delta answers "what changed"; a residual answers "what still blocks this judgment".

## 4. Decoupled adapters

`semantic_residual_v0.py` imports only canonicalization plus `semantic_kernel_v0`.

`semantic_residual_adapters_v0.py` depends only on the kernel and residual layer. Existing semantic producers do not import the residual subsystem and therefore retain their current authority and behavior.

Adapters project existing results into one common residual profile:

- application outcomes: `REJECTED`, `FAILED`, `PARTIAL`, `UNKNOWN_COMMIT`, `LAW_VIOLATION`;
- inference: `PROOF_REQUIRED` and countermodels;
- proof boundary: scope, activity, proof strength, verifier trust;
- composition/abstraction: exact or relation-scoped field divergence;
- epistemic: missing knowledge;
- causal: staging/causal hazards;
- refinement: unmet refinement obligations;
- governance: missing authority.

No adapter changes the source result. It only derives a new Field.

## 5. Determinism and provenance

Residual obstruction rows are canonicalized, deduplicated, and sorted by canonical JSON. Source and judgment are independently content-addressed. Consequently equal `(domain, judgment, source, obstruction-set)` inputs produce equal residual field hashes independent of insertion order.

Aggregation does not erase child evidence: an open child residual is represented by an obstruction that contains the child residual hash and child judgment hash.

## 6. CUOFC boundary

CUOFC may motivate the mathematical notion of residual and may define a research correspondence `CUOFC residual ⇀ TEV SemanticFieldV0[residual]`.

CUOFC is **not** imported by the TEV residual implementation, is not a runtime dependency, and has no language, ABI, truth, certification, release, or promotion authority over TEV Script.

## 7. Non-goals

V0 intentionally adds:

- no source keyword;
- no V1 grammar change;
- no IR V2/V3 opcode;
- no runtime ABI change;
- no ambient planner/agent policy;
- no scalar universal error metric;
- no assumption that every open residual is automatically reducible.

A later surface-language feature may expose residualization only after this semantic interface proves useful without destabilizing V1.
