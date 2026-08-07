# Runtime porting checklist

A new runtime language is not conformant merely because it can read the schema.
It must demonstrate:

1. strict UTF-8/JSON input with duplicate-key rejection;
2. exact tagged `Int` and normalized `Rat` values;
3. Unicode-scalar key ordering and ASCII canonical JSON escaping;
4. all normative canonical JSON vectors and SHA-256 values;
5. SHA-256 semantic program verification;
6. strict IR, scenario and receipt structure;
7. every V0.2 opcode and pure function;
8. FIFO event-chain semantics;
9. instruction and event budgets;
10. fail-closed missing capabilities;
11. no implicit physical effects;
12. exact `player.basic.v1` and `matrix.full.v1` receipt bytes;
13. tampering, malformed-value, duplicate-key and numeric-boundary negatives.

Suggested implementation order:

```text
strict JSON loader
→ portable value model
→ canonical JSON/hash
→ IR validation
→ stack VM
→ capability ABI
→ event queue
→ conformance receipt
→ host adapters
```

Future Rust, Java, Kotlin, Swift and Go runtimes should begin here rather than
translating Python or C# implementation details.

## Language-completeness additions

A conforming runtime must also: (14) reject the shared `language-negative-v1` corpus with `TEVS_IR_FLOW_INVALID`; (15) implement typed acyclic CFG/stack verification before runtime construction; (16) reject non-canonical invocation and capability-binding ids without trimming; (17) preserve the V0.2 operator/type matrix; and (18) pass all four positive receipt vectors after those negative boundaries.
