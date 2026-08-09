# TEV Script V1 tooling architecture

Status: architecture guide for the V1 implementation candidate.

TEV Script tooling is divided by **authority level**, not by UI surface.

The core rule is:

> Tooling may duplicate lexical presentation rules, but it must not silently create a second semantic authority for linking, typing, effects, lowering or runtime execution.

---

# 1. Authority layers

## Layer A — lexical/editor presentation

Safe to implement independently when it cannot accept/reject TEV programs:

```text
syntax highlighting
comment markers
bracket pairing
indentation hints
snippets
file associations
```

Current implementation:

```text
editors/vscode/
```

This layer is non-normative.

## Layer B — deterministic build metadata

May select explicit inputs/targets but must not change program meaning:

```text
TEV_SCRIPT_PROJECT_V1
project-check
build
target override
manifest_hash
project_input_hash
artifact commit policy
```

Current implementation:

```text
tev_script/project_v1.py
schemas/tev_script_project_v1.schema.json
docs/V1_PROJECT_MANIFEST.md
```

The canonical linker remains authoritative over which source is the script root, module ids, imports and visibility.

## Layer C — compiler semantics

Must use the canonical V1 compiler pipeline:

```text
parse
link
name resolution
type checking
purity/effects/events
constant evaluation
behavior composition
linked-program canonicalization
IR V2 lowering boundary
IR V2/V3 lowering
```

Current implementation:

```text
tev_script/pipeline_v1.py
TEV_SCRIPT_LINKED_PROGRAM_V1
```

Any future LSP or IDE semantic service should call this layer rather than reimplementing it.

## Layer D — runtime validation/evidence

Must use the canonical IR V3 contracts:

```text
IR validator
closed type table
CFG verifier
scripted conformance
runtime checkpoint
```

Current read-only CLI:

```powershell
python -m tev_script.runtime_cli_v3
```

## Layer E — host authority

Cannot be supplied by generic editor/build tooling:

```text
real capability providers
filesystem/network/device authority
production signing keys
installed-update durable store
rollback-resistant monotonic storage
```

These belong to explicit host adapters and governance contracts.

---

# 2. Current tooling map

## Source CLI

```text
tev-script
    certified V0.2 command

tev-script-v1
    additive V1 candidate command
```

V1 commands:

```text
check
project-check
link
boundary
compile
build
lower-irv2
lower-irv3
```

## Project manifests

```text
TEV_SCRIPT_PROJECT_V1
```

Properties:

```text
explicit finite source set
no globbing
no network/registry resolution
portable relative paths
source content hashing
input-drift recheck
```

## Descriptor

Query:

```powershell
python -m tev_script.describe_v1
```

Schema:

```text
TEV_SCRIPT_DESCRIPTOR_V3
```

Purpose:

```text
language/profile discovery
budgets
boundaries
runtime target availability
build-tooling contracts
candidate/stable state
```

## Runtime validation/conformance

```powershell
python -m tev_script.runtime_cli_v3 describe Program.ir.json
python -m tev_script.runtime_cli_v3 validate Program.ir.json
python -m tev_script.runtime_cli_v3 conformance Program.ir.json scenario.json
```

No generic ambient-capability `run` command exists.

## VS Code

```text
editors/vscode/
```

Static-only assets:

```text
TextMate grammar
language configuration
snippets
```

No executable extension code.

---

# 3. Why formatter is deferred

A production formatter must preserve comments/trivia and semantic source intent.

The current compiler AST is semantic and does not constitute a lossless concrete syntax tree. Formatting from it could discard comments or normalize source distinctions that tooling should preserve.

Therefore the current rule is:

```text
formatter = DEFERRED
until lossless syntax/trivia representation exists
```

This is preferable to shipping a formatter that damages source.

---

# 4. Future LSP design

A future language server should be an adapter over compiler data, not a competing compiler.

Recommended architecture:

```text
editor document snapshots
    -> TEV Script V1 source loader
    -> canonical V1 parse/link/static pipeline
    -> existing SourceSpan/Diagnostic values
    -> LSP diagnostic/range conversion
```

Possible additional compiler-backed queries:

```text
resolved declaration
resolved nominal type
capability requirement set
linked semantic hash
IR V2 lowering blockers
module import graph
behavior composition closure
```

The LSP should not:

```text
invent permissive type inference
resolve imports using editor filesystem search
execute capabilities
change compiler budgets
accept syntax rejected by the compiler
```

---

# 5. Evidence-safe artifact emission

Compilation outputs that include a lowering receipt use:

```text
EVIDENCE_SAFE_RECEIPT_LAST_V1
```

See:

```text
docs/V1_ARTIFACT_COMMIT.md
```

The receipt is installed after the IR and acts as the final commit witness.

This is build evidence, not language semantics.

---

# 6. Machine-readable discovery vs normative specs

Machine descriptor:

```text
TEV_SCRIPT_DESCRIPTOR_V3
```

Normative language source contracts:

```text
spec/TEV_SCRIPT_V1_LEXICAL_PROFILE.md
spec/TEV_SCRIPT_V1.ebnf
spec/TEV_SCRIPT_V1_SEMANTIC_CONTRACT.md
spec/TEV_SCRIPT_V1_LINK_MODEL.md
spec/TEV_SCRIPT_V1_BUDGETS.md
```

The descriptor reports the implemented profile. It does not supersede these specs.

---

# 7. Design rule for new tooling

Before adding a tool, classify it:

```text
Does it only present existing syntax?
    -> lexical tooling may be independent

Does it choose/build exact inputs?
    -> deterministic build contract

Does it answer what a program means?
    -> must call canonical compiler semantics

Does it execute a program?
    -> must use validated runtime IR

Does it grant external authority?
    -> requires explicit host/governance contract
```

This keeps IDE convenience from quietly becoming a second language implementation.
