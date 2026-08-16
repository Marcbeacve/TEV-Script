# TEVScript MAX V3 — Independent JavaScript Runtime Design

Date: 2026-08-16

## Objective

Provide a second, independent implementation of the admitted Program IR V5 `semantic_process` runtime so Python is not semantic authority by implementation monopoly.

## Boundary

The JavaScript runtime consumes only already-compiled Program IR V5 plus Process Checkpoint V1. It does not parse TEVScript source, acquire host capabilities, commit physical effects, or call Python. It uses Node standard-library `crypto` only.

It independently implements:

- strict JSON input with duplicate-key, float, negative-zero and unsafe-integer rejection;
- Python-compatible canonical JSON with sorted keys and `ensure_ascii` escaping;
- Field/fact/Transformation/Instruction/Program/Checkpoint hash validation;
- `Apply` semantics including explicit `result_profile`;
- bounded `apply`, `branch_fact`, `jump`, `halt` execution;
- Omega Epoch/Continuation identity and checkpoint chaining;
- canonical quantum-result hashing.

## Admission criterion

For the same admitted IR/checkpoint:

```text
canonical(PythonResult) == canonical(JavaScriptResult)
```

including Field hash, result hash, continuation hash, checkpoint hash and quantum hash.

The runtime is an independent implementation, not a translation of Python object internals at runtime. Compiler/source semantics remain outside this runtime.

## Negative controls

- malformed/tampered Program IR hash fails before execution;
- duplicate JSON keys fail before validation;
- floating JSON numbers, negative zero and unsafe integers fail;
- halted checkpoint cannot resume;
- proof-open transformations remain non-executable;
- object keys such as `__proto__` are treated as ordinary canonical data, never host-language object authority.

No parity result grants promotion or publication authority.
