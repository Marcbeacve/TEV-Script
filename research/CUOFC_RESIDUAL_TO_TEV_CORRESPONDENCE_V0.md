# CUOFC finite Residual -> TEV Semantic Residual correspondence V0

Status: **research-only, post-V1 experimental, non-normative**.

## Boundary

This correspondence is intentionally implemented in `research/cuofc_residual_correspondence_v0.py`, not in `tev_script/semantic_residual_v0.py`.

Allowed direction:

`research correspondence -> CUOFC construct model + TEV residual semantic API`

Forbidden direction:

`TEV residual core -> CUOFC`

CUOFC therefore has no TEV Script language, runtime, ABI, truth, certification, release, or promotion authority.

## Finite residual realization

The corresponding CUOFC finite fragment treats a residual as a finite set of outstanding judgment-relative obligations. The research translator expects a CUOFC `Construct(kind="residual")` with:

- `domain`;
- stable `judgment_id`;
- canonical `judgment` definition independent of the current outstanding set;
- finite `outstanding` token list;
- optional TEV `context_hash` and `law_hash` boundary identities.

Each outstanding token is encoded as one content-addressed TEV obstruction:

`correspondence.outstanding(token)`

with a stable token hash and dependency reference. The TEV source Field also binds the complete CUOFC construct hash and current outstanding snapshot.

The correspondence result is `DERIVED`, never normative, and targets `TEV.SemanticResidualFieldV0`.

## Closure preservation

An empty CUOFC outstanding set maps to a TEV `CLOSED` residual. A non-empty set maps to `OPEN`.

This preserves finite nullity without claiming that TEV closure means omniscience or complete world equality.

## Progress preservation

When domain, judgment, context and laws are fixed, the explicit token encoding preserves the finite subset order:

`{a,b} -> {b}` maps to TEV `REDUCED`.

`{a} -> {}` maps to TEV `CLOSED`.

Equal outstanding sets map to `UNCHANGED`; proper supersets map to `REGRESSED`; incomparable sets map to `CHANGED`.

TEV adds one stricter case absent from the bare finite-set fragment: if judgment, context or law identity changes, progress is `INCOMPARABLE` rather than being inferred from set cardinality.

## Non-circularity

The research adapter may import the TEV Residual API because its job is to study correspondence. The production residual modules are statically validated to contain no CUOFC, research, IA-TEV, planner, or agent dependency.

This preserves the authority direction:

CUOFC may motivate and test a mathematical structure; independently governed TEV semantics define the executable representation.

## Focal verification

The correspondence campaign requires:

- open finite residual -> open TEV Residual Field;
- empty finite residual -> closed TEV Residual Field;
- finite strict subset -> TEV `REDUCED`;
- boundary change -> TEV `INCOMPARABLE`;
- `NON_NORMATIVE_RESEARCH_ONLY` authority class.

No V1 grammar, IR, ABI or runtime behavior changes follow from this correspondence.
