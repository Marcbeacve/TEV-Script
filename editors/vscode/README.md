# TEV Script — VS Code static language support

This directory contains a **zero-runtime, zero-dependency** VS Code language package for `.tevs` authoring.

It intentionally provides only editor services that can be implemented lexically without duplicating TEV Script semantics:

```text
.tevs file association
TextMate syntax highlighting
# line comments
bracket / quote pairing
basic indentation
V1 snippets
```

It deliberately does **not** provide:

```text
an independent parser
a second type checker
a formatter
an embedded LSP implementation
code execution
capability discovery
network/package resolution
```

## Why no formatter yet?

The current source frontend does not preserve comments/trivia as a lossless syntax tree. Formatting from the semantic AST would therefore risk deleting or moving comments.

A production formatter should be added only after TEV Script has a lossless concrete-syntax/trivia representation or another proof that comments/source intent are preserved.

## Canonical LSP

The repository now provides an **external thin LSP adapter**:

```powershell
tev-script-v1-lsp
```

or with an explicit project manifest:

```powershell
tev-script-v1-lsp --project .\tevscript.project.json
```

The VS Code package does not embed or reimplement that server. The external server delegates diagnostics to the canonical V1 parser/linker/static-semantic pipeline and translates the existing source spans to LSP UTF-16 positions. See `docs/V1_LSP.md`.

This keeps the architecture:

```text
VS Code lexical package -> presentation only
external V1 LSP         -> protocol adapter only
V1 compiler pipeline    -> semantic authority
```

Until an optional VS Code client launcher is added, configure your editor/LSP client to start `tev-script-v1-lsp` explicitly. The static package remains useful independently for highlighting and snippets.

## Compiler commands

Single explicit source set:

```powershell
tev-script-v1 check .\Program.tevs
```

Project manifest:

```powershell
tev-script-v1 project-check .\tevscript.project.json
```

## Install for local development

This folder is intentionally a static VS Code extension package. Open it in VS Code and use the normal Extension Development Host workflow, or package it with the VS Code extension tooling of your choice.

No generated extension bundle is committed here.

## Language version coverage

The lexical grammar recognizes the V0.2 core plus V1 additions:

```text
module/import/export
record/enum
fn
behavior/use
Option/Result
Some/None/Ok/Err
match
for/in
observation/effect
->
=>
..
::
```

Semantic validity is still determined by the compiler, not by highlighting.

## Source of truth

Normative V1 language contracts live under:

```text
spec/TEV_SCRIPT_V1_LEXICAL_PROFILE.md
spec/TEV_SCRIPT_V1.ebnf
spec/TEV_SCRIPT_V1_SEMANTIC_CONTRACT.md
```

The editor assets and LSP transport layer are non-normative tooling. Neither may redefine TEV Script semantics.
