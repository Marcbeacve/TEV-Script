# TEV Script V1 canonical LSP

`tev-script-v1-lsp` is a thin Language Server Protocol adapter over the existing TEV Script V1 compiler pipeline.

It is deliberately **not** a second parser, linker, type checker or effect system.

```text
editor text
   -> LSP transport adapter
   -> canonical parse_v1_bytes
      or canonical analyze_v1_mapping
   -> existing TevScriptError / SourceSpan
   -> exact LSP diagnostic conversion
```

## Scope

Implemented candidate services:

- JSON-RPC 2.0 over stdio with `Content-Length` framing;
- `initialize`, `shutdown`, `exit`;
- full-text document synchronization;
- `textDocument/didOpen`;
- `textDocument/didChange`;
- `textDocument/didSave`;
- `textDocument/didClose`;
- push diagnostics through `textDocument/publishDiagnostics`;
- parser/syntax-budget diagnostics for standalone documents;
- full link/static-semantic diagnostics when an explicit `TEV_SCRIPT_PROJECT_V1` is supplied;
- unsaved open-document overlays over the explicit project source set;
- exact conversion from TEV Script code-point offsets to LSP UTF-16 positions.

Not implemented by this server:

- an independent grammar;
- independent import/name/type/effect logic;
- arbitrary code execution;
- arbitrary host capability injection;
- workspace file discovery or globs;
- network/package registry resolution;
- formatting;
- refactoring that rewrites source;
- completion/hover based on a second semantic index.

Those omissions are intentional. Editor intelligence that requires semantics must consume the canonical V1 semantic model rather than reconstruct it independently.

## Start

Standalone parser diagnostics:

```powershell
tev-script-v1-lsp
```

Full project diagnostics:

```powershell
tev-script-v1-lsp --project .\tevscript.project.json
```

The `--project` path is explicit. The LSP does not search parents, scan folders or infer a project.

## Position encoding

TEV Script source is UTF-8, while the lexer stores Python Unicode code-point offsets. LSP clients conventionally use UTF-16 positions.

The server advertises:

```text
positionEncoding = utf-16
textDocumentSync.change = Full
```

Every diagnostic range is calculated from the exact source text by converting code-point offsets into UTF-16 code units. This is necessary for correct positions after non-BMP characters such as emoji.

No direct reuse of TEV Script `column` as an LSP `character` is permitted.

## Project mode

With `--project`, every analysis reloads the manifest and its current on-disk source files, then replaces any open project documents with their unsaved in-memory text before calling `analyze_v1_mapping`.

Therefore:

```text
manifest source list = explicit project boundary
open editor text     = temporary authoring overlay
link/type/effect      = canonical compiler authority
LSP                   = transport + position conversion only
```

The server clears prior project diagnostics before publishing the current compiler result so an error moved from one module to another cannot leave stale markers.

## Why the VS Code package remains static

`editors/vscode` remains a zero-runtime TextMate/snippet package. It does not embed a JavaScript or TypeScript copy of the compiler.

An editor client may launch `tev-script-v1-lsp` as an external process. Keeping the protocol server in the Python reference package preserves one semantic authority while allowing any LSP-capable editor to integrate it.

## Validation

`tests/test_v1_lsp.py` covers:

- LSP message framing;
- Unicode payloads;
- UTF-16 conversion including emoji;
- initialize/shutdown/exit;
- parse-only diagnostics;
- diagnostic clearing after repair;
- project-mode missing-import diagnostics from the canonical linker;
- diagnostic clearing on close.

The LSP remains a V1 candidate surface until the exact clean HEAD passes `RUN_TEV_SCRIPT_V1_PRECERTIFY.py` and `RUN_TEV_SCRIPT_V1_CERTIFY_FULL.py`.
