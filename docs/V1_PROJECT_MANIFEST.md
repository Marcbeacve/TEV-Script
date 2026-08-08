# TEV Script V1 project manifest

Status: **build-tooling contract for the V1 implementation candidate**.

The V1 language intentionally receives an explicit finite source set. A project manifest is a reproducible convenience for supplying that set; it does not change import semantics, module identity or the linked-program semantic hash.

Schema:

```text
TEV_SCRIPT_PROJECT_V1
```

JSON Schema:

```text
schemas/tev_script_project_v1.schema.json
```

## Shape

```json
{
  "schema": "TEV_SCRIPT_PROJECT_V1",
  "language_version": "1.0.0",
  "default_target": "auto",
  "sources": [
    "main.tevs",
    "model.tevs",
    "rules.tevs"
  ]
}
```

Fields are exact; unknown fields fail closed.

## Sources

`sources` is the complete build input set.

Rules:

- 1..257 source entries;
- each entry ends in `.tevs`;
- paths are manifest-relative;
- `/` is the portable separator;
- absolute and drive-qualified paths are rejected;
- `.` / `..` segments are rejected;
- paths resolving outside the manifest directory are rejected;
- duplicate manifest paths are rejected;
- aliases resolving to the same physical file are rejected;
- no globs;
- no recursive directory scan;
- no registry/network lookup.

The linker still requires exactly one script root and validates the reachable module closure. The project manifest does not assign module ids.

## Source order

Manifest source order is not semantic.

The loader normalizes source paths lexically before producing its canonical project identity. Therefore these manifests describe the same project build configuration:

```json
{"schema":"TEV_SCRIPT_PROJECT_V1","language_version":"1.0.0","default_target":"auto","sources":["main.tevs","model.tevs"]}
```

```json
{"schema":"TEV_SCRIPT_PROJECT_V1","language_version":"1.0.0","default_target":"auto","sources":["model.tevs","main.tevs"]}
```

The linked-program layer independently proves source input order does not change language semantics.

## Targets

`default_target` is exactly one of:

```text
auto
irv2
irv3
```

`auto` means:

```text
IR V2 boundary lowerable
    -> TEV_SCRIPT_PROGRAM_IR_V2
otherwise
    -> TEV_SCRIPT_PROGRAM_IR_V3
```

A CLI `--target` override may select another target for one build without changing the manifest.

Forcing `irv2` still fails closed when the linked program is not losslessly lowerable.

## Build identities

Project metadata has two explicit identities that are **not** the TEV program semantic hash.

### `manifest_hash`

SHA-256 over the canonical normalized manifest:

```text
schema
language version
default target
sorted relative source paths
```

It identifies the build configuration.

### `project_input_hash`

SHA-256 over:

```text
manifest_hash
+
for every normalized source:
    relative path
    SHA-256 source bytes
    byte count
```

It identifies one exact project input set.

### `linked_semantic_hash`

This remains the canonical TEV Script program meaning after parse/link/static normalization.

The distinction is intentional:

```text
rename source file only
    project_input_hash may change
    linked_semantic_hash should remain unchanged

change program semantics
    project_input_hash changes
    linked_semantic_hash changes
```

## TOCTOU boundary

`tev-script-v1 build` loads and hashes the manifest/source files, performs the compiler analysis, then re-loads the project before writing artifacts.

If the manifest or any source bytes changed during that operation, build fails with a project-input change diagnostic rather than emitting an artifact whose receipt describes a different source snapshot.

This is a local build consistency boundary. It is not a hostile-filesystem transactional guarantee.

## CLI

Check:

```powershell
tev-script-v1 project-check .\examples\v1\ecosystem\tevscript.project.json
```

Build using manifest default target:

```powershell
tev-script-v1 build `
  .\examples\v1\ecosystem\tevscript.project.json `
  -o .\Ecosystem.ir.json
```

Build and emit lowering receipt:

```powershell
tev-script-v1 build `
  .\examples\v1\ecosystem\tevscript.project.json `
  -o .\Ecosystem.ir.json `
  --receipt .\Ecosystem.lowering.json
```

Override target for one build:

```powershell
tev-script-v1 build `
  .\examples\v1\ecosystem\tevscript.project.json `
  --target irv3 `
  -o .\Ecosystem.ir.json
```

## What the manifest deliberately does not contain

The V1 project file does not define:

- package versions;
- dependency registries;
- remote URLs;
- compiler plugin execution;
- host capability implementation paths;
- signing keys;
- output directory policy;
- Unity scene references;
- environment-variable expansion.

Those would introduce additional authority/reproducibility surfaces and require separate contracts.
