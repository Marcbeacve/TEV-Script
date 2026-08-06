# AGENTS — TEV Script repository authority

## Mandatory invariants

- Grammar, static semantics, IR, value model, ABI, canonical hashing, and
  conformance receipts are the language authority.
- Python, JavaScript, C#, Unity, and future runtimes are implementations, not
  semantic authorities.
- No runtime may interpret `.tevs` source in production.
- No implicit physical effect is permitted. Every host effect crosses an
  explicit capability.
- Integer and rational arithmetic remains exact until a host capability
  explicitly converts it.
- Missing capabilities, exhausted budgets, malformed IR, and hash mismatches
  fail closed.
- `.tev` and `.tevg` remain the causal and general workflow kernels.
- Do not duplicate or replace those kernels inside TEV Script.

## Repository workflow

- Default publication mode: branch plus draft pull request.
- Branch prefix: `agent/`.
- No merge, release, tag, or stable promotion without explicit authorization.
- No GitHub Actions. Use local certification and external receipts.
- Preserve exact HEAD/tree identities in certification evidence.
