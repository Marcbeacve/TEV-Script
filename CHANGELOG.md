# Changelog

## 0.2.0-preview — hardened candidate

- Defines `TEV_SCRIPT_PROGRAM_IR_V2` as language-neutral authority.
- Adds exact portable `Int` and `Rat` representations.
- Adds the bounded synchronous capability ABI.
- Adds conformant Python and JavaScript runtimes.
- Adds a self-contained C# runtime candidate without claiming compilation.
- Adds strict Draft 2020-12 schemas for program, scenario and receipt.
- Adds `TEV_CANONICAL_JSON_V1` and normative vectors.
- Adds strict Python and JavaScript JSON input boundaries.
- Adds `matrix.full.v1` to cover the complete V0.2 operational surface.
- Makes the npm distribution self-contained and executable after packing.
- Adds Python/JavaScript byte-identical evidence for four scenarios.
- Emits CLI artifacts as deterministic UTF-8/LF bytes on every host.
- Makes child-process log forwarding safe under redirected CP1252/ASCII stdio.

This entry is not a stable release declaration.
