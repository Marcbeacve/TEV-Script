# Canon

Normative order for TEV Script `0.2.0`:

1. `DESIGN_DECISION.json` and `descriptor.json` define project/governance boundary.
2. `spec/TEV_SCRIPT_V0_2.ebnf` and `spec/SOURCE_LEXICAL_GRAMMAR_V1.md` define accepted source.
3. `spec/STATIC_SEMANTICS_V1.md` defines source typing, names, events, pure functions and capability compilation.
4. `spec/PORTABLE_VALUE_MODEL_V1.md` defines semantic values.
5. `spec/CANONICAL_JSON_PROFILE_V1.md` defines canonical bytes and hashes.
6. `schemas/tev_script_program_ir_v2.schema.json` plus `spec/IR_OPERATIONAL_SEMANTICS_V1.md` define structural and operational IR V2.
7. `spec/RUNTIME_ABI_V1.md` defines runtime loading, canonical invocation/binding ids, capabilities and event execution.
8. `schemas/tev_script_capability_catalog_v1.schema.json` and `catalogs/portable_capabilities_v1.json` define portable/default capability signatures and typed extension format.
9. `spec/CONFORMANCE_PROTOCOL_V1.md` plus scenario/receipt schemas define positive conformance.
10. `conformance/canonical.vectors.json`, all four positive scenarios/receipts, and `conformance/language-negative-v1.json` are normative executable evidence.
11. `docs/LANGUAGE_COMPLETENESS_V1.md` records the closure criteria; `docs/VALIDATION.md` records observed certification state.

Reference implementations and adapters must conform to this contract and do not redefine it. A runtime is not conformant merely because it accepts the schema: it must pass canonical vectors, positive byte receipts, the shared negative IR-flow corpus, and ABI fail-closed boundaries.
