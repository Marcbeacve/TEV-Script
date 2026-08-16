# TEVScript MAX 3.0.0 — Semantic Process Source Profile

Status: normative implementation candidate. No stable/publication authority.

## Source form

The first native V3 source profile is a finite, line-oriented semantic-process language that lowers exactly to `TEV_SCRIPT_PROGRAM_IR_V5_SEMANTIC_PROCESS_V1`.

```text
process <ProgramId> version "3.0.0";
authority <sha256-hex>;
quantum_steps <1..1000000>;

fact <FactName> = <relation-id> <strict-canonical-json-array>;
...

field <profile-id> = [<FactName>, ...];

transform <TransformId> effects <sha256-hex> resources <sha256-hex>
          [profile <result-profile-id>]
          remove [<FactName>, ...] add [<FactName>, ...];
...

label <Label> = apply <TransformId> <NextLabel>;
label <Label> = branch_fact <FactName> <PresentLabel> <AbsentLabel>;
label <Label> = jump <TargetLabel>;
label <Label> = halt;
...

entry <Label>;
```

Blank lines and lines beginning with `#` are nonsemantic. Whitespace between tokens is nonsemantic. Fact/transform/label declaration order is nonsemantic; labels are resolved symbolically and the compiler emits a canonical label order by lexical label name. `entry` names the entry label.

## Static semantics

- program, fact, transform and label names are unique;
- every referenced fact/transform/label exists;
- the initial `field` contains unique declared facts;
- fact argument arrays use the existing strict TEV JSON parser: duplicate object keys, floating-point structural numbers, non-standard constants and noncanonical structural integers fail closed before semantic hashing;
- transformation add/remove sets contain unique declared facts and cannot overlap;
- optional `profile <id>` makes the Transformation produce a Field with that exact profile; absence preserves the input Field profile;
- effect/resource hashes are explicit 64-hex bindings, not grants;
- proof-open transformations are not syntax in this first executable source profile;
- every label resolves to one closed IR V5 instruction;
- `quantum_steps` is finite and mandatory;
- cycles between labels are permitted because the runtime enforces epoch suspension;
- source semantic identity is derived from the resolved canonical source model, never from file path or original whitespace.

## Canonical source model

The compiler resolves names before hashing. The semantic source object contains:

```text
schema = TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE_MODEL_V1
language_version = 3.0.0
program_id
facts sorted by fact name
field profile + sorted fact names
transformations sorted by transform id, including optional result_profile
labels sorted by label name
entry label
quantum_steps
authority_hash
```

`source_semantic_hash` is SHA-256 of that canonical model and is passed to IR V5. The independent Source→IR validator reconstructs the same `result_profile` lowering and must admit the exact emitted IR before the V3 CLI may write a Program IR V5 artifact.

## Compatibility

The V3 product exposes V2 only through the explicit `tev-script-v3 v2 ...` compatibility lane. V2 source remains language version `2.0.0`, retains Program IR V4 identity and is delegated to the unchanged V2 CLI/runtime. The V3 semantic-process parser never rewrites a V2 program into V3 semantics.
