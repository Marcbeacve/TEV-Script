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
an LSP implementation
code execution
capability discovery
network/package resolution
```

## Why no formatter yet?

The current source frontend does not preserve comments/trivia as a lossless syntax tree. Formatting from the semantic AST would therefore risk deleting or moving comments.

A production formatter should be added only after TEV Script has a lossless concrete-syntax/trivia representation or another proof that comments/source intent are preserved.

## Why no independent LSP?

A language server that reimplemented import/name/type/effect semantics would create a second semantic authority and could disagree with the compiler.

A future LSP should call the canonical V1 compiler pipeline and translate its existing source spans/diagnostics into editor protocol messages.

Until then, use the compiler directly:

```powershell
tev-script-v1 check .\Program.tevs
```

or, for a project manifest:

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

The editor assets are non-normative tooling and are tested only for structural/lexical alignment with that surface.
