# TEVScript MAX 3.1 Total-Core — JavaScript parity amendment

Date: 2026-08-16
Status: NORMATIVE AMENDMENT TO `2026-08-16-tevscript-max-3-1-total-core-design.md`

This amendment removes one ambiguity found during design self-review.

## Independent JavaScript authority boundary

`runtime_js_v31` MUST implement the governed Total-Core JavaScript runtime independently from the normative Program IR V4/V5 specifications. It MUST NOT delegate any V4 or V5 execution to Python and MUST NOT assume that a pre-existing JavaScript Program IR V4 runtime exists.

Reusable JavaScript helpers already present in the repository MAY be shared only when they are deterministic implementation utilities whose semantics are independently pinned by the same normative schemas/vectors. Such reuse does not make the reused implementation language authority.

The minimum Stable Admission parity set MUST include at least one governed child artifact for each embedded V4 profile admitted by Total-Core:

- pure;
- recursive;
- effects.

For each profile Python and JavaScript MUST agree byte-for-byte on:

- validated child `program_ir_hash`;
- child run result/receipt projection used by Total-Core;
- generated bridge fact bytes and `fact_hash`;
- derived bridge transformation hash;
- resulting Field hash;
- Total-Core checkpoint hash;
- Omega continuation/result/state/effects/observations/resources hashes;
- rejection code/class for governed tamper negatives.

If the complete normative V4 profile cannot be implemented independently in JavaScript for 3.1, Stable Admission remains `HOLD`; the gate MUST NOT silently reduce the advertised Total-Core profile.
