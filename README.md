# TEV Script

TEV Script is a bounded, typed, portable language for reactive behaviour and
explicit host capabilities. The language is not defined by Python, JavaScript,
C#, Unity, or any other implementation language.

```text
.tevs source
    -> typed frontend
    -> TEV_SCRIPT_PROGRAM_IR_V2
    -> conforming runtime
       |- Python reference
       |- JavaScript ES2022 reference
       |- C#/.NET conformant reference (observed Windows/.NET 10)
       `- future Rust, Java/Kotlin, WASM, and other hosts
```

## Authority

The normative authority is the combination of:

- `spec/TEV_SCRIPT_V0_2.ebnf`;
- `spec/PORTABLE_VALUE_MODEL_V1.md`;
- `spec/CANONICAL_JSON_PROFILE_V1.md`;
- `spec/RUNTIME_ABI_V1.md`;
- the three Draft 2020-12 schemas under `schemas/`;
- canonical JSON vectors;
- conformance scenarios and byte-identical receipts.

Implementations are replaceable. A runtime becomes conformant only after it
passes the canonical vectors and reproduces every authoritative receipt byte
for byte.

## Status

```text
LANGUAGE_VERSION=0.2.0
IR_SCHEMA=TEV_SCRIPT_PROGRAM_IR_V2
STATUS=PREVIEW
STABLE_RELEASE=NO
PYTHON_RUNTIME=CONFORMANT_REFERENCE
JAVASCRIPT_RUNTIME=CONFORMANT_ES2022_REFERENCE
CSHARP_RUNTIME=CONFORMANT_DOTNET_REFERENCE_OBSERVED_WINDOWS_NET10
UNITY_ADAPTER=DESIGNED_NOT_IMPLEMENTED
```

Python and JavaScript currently reproduce four authoritative scenarios:

```text
PLAYER_PROGRAM_HASH=f18d1b2428b96bf8c859463ab62a431c654933e65e23c3d8183335506d5adb5d
PLAYER_RECEIPT_HASH=b275ccc6530ad84c0f96320ba1c8893b401638a926a99a78479d99fbd3c4aba5
MATRIX_PROGRAM_HASH=899c555b1825e340e53a53ad21aaf7e8fb7a4f7fe53e26f0a66b196515ed2393
MATRIX_RECEIPT_HASH=70df629159b6088aa3807deea217d4cdb06f28a41042aac1f6ebff6332179500
PLAYER_IDLE_RECEIPT_HASH=647d3211f7411b88c155d658ba4c9494482378cde75c9f427dc4e38475acd17c
EVENT_CHAIN_PROGRAM_HASH=a362d9b7e2850c8327eb0f6a4cbebf949cb6edb82fb493f980a8c5c8c078aea5
EVENT_CHAIN_RECEIPT_HASH=5fcbd07512192ec298ff18bc313c71418e079e04d303aa3514a49ab91462371d
```

The campaign exercises both `if` branches, all V0.2 operators and pure
functions, every portable value kind, typed event arguments, Unicode, exact
`Int`/`Rat`, direct capability calls, and bounded local event chaining.

## Validate

Windows:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_PORTABLE_V0_2.ps1 `
  -Python "C:\path\to\python.exe"
```

Portable command:

```text
python RUN_PORTABLE_CONFORMANCE.py
```

Expected terminal witness:

```text
CONFORMANCE_SCENARIOS=4
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
STRICT_JSON_INPUT_BOUNDARY=PASS
JSON_SCHEMA_VALIDATION=PASS
CSHARP_PORTABLE_STATIC_BOUNDARY=PASS
CSHARP_COMPILATION=NOT_PROBED_BY_PORTABLE_RUNNER
TEV_SCRIPT_PORTABLE_V0_2=PASS_PYTHON_JAVASCRIPT
```

## Packages

Python frontend and reference runtime:

```text
python -m tev_script.cli check examples/Player.tevs
python -m tev_script.cli compile examples/Player.tevs --output Player.ir.json
python -m tev_script.cli conformance examples/Player.tevs conformance/player.scenario.json
```

JavaScript runtime and distribution checks:

```text
cd javascript
npm test
npm run conformance
```

C# runtime source is under `runtimes/csharp/TevScript.Core`. It is independent
of `UnityEngine` and `Marcbeacve.TevLnu.Core`. The observed Windows/.NET 10
campaign reproduces all four authoritative receipts byte for byte and passes
the C# negative-boundary campaign. Unity remains a host adapter, not the
language authority.

## Relationship with the existing TEV languages

```text
.tevs  everyday bounded reactive behaviour
.tev   governed causal actions
.tevg  finite multi-entity workflows
```

Future lowering from `.tevs` governed constructs must target the existing
causal/general IRs rather than creating a second causal kernel.

## Publication boundary

This repository contains no GitHub Actions workflow. Validation is local and
receipt-based. Publication uses a feature branch and draft pull request. No
merge, tag, stable release, or promotion is authorized by this seed.

Validation details: `docs/VALIDATION.md`.

## TEV Script V0.2 language closure

The V0.2 source/IR/runtime contract now has complete lexical grammar, static semantics, operational IR semantics, typed capability-catalog extension, a pre-execution typed CFG verifier, canonical ABI identifiers, and a shared Python/JavaScript/C# negative corpus. `stable` remains false; language completeness is not a stable-release or production-security claim.
