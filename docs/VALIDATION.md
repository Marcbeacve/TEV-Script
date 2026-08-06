# Validation

## Current certified surface

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CANONICAL_JSON_VECTORS=PASS
STRICT_JSON_INPUT_BOUNDARY=PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
JSON_SCHEMA_VALIDATION=PASS
POWERSHELL_MATERIALIZER_STATIC_STRUCTURE=PASS
CSHARP_PORTABLE_STATIC_BOUNDARY=PASS
```

Authoritative hashes:

```text
PLAYER_PROGRAM_HASH=f18d1b2428b96bf8c859463ab62a431c654933e65e23c3d8183335506d5adb5d
PLAYER_RECEIPT_HASH=b275ccc6530ad84c0f96320ba1c8893b401638a926a99a78479d99fbd3c4aba5
MATRIX_PROGRAM_HASH=899c555b1825e340e53a53ad21aaf7e8fb7a4f7fe53e26f0a66b196515ed2393
MATRIX_RECEIPT_HASH=70df629159b6088aa3807deea217d4cdb06f28a41042aac1f6ebff6332179500
PLAYER_IDLE_RECEIPT_HASH=647d3211f7411b88c155d658ba4c9494482378cde75c9f427dc4e38475acd17c
EVENT_CHAIN_PROGRAM_HASH=a362d9b7e2850c8327eb0f6a4cbebf949cb6edb82fb493f980a8c5c8c078aea5
EVENT_CHAIN_RECEIPT_HASH=5fcbd07512192ec298ff18bc313c71418e079e04d303aa3514a49ab91462371d
```

The runner validates all three JSON schemas with a Draft 2020-12 validator when
`jsonschema` is available. Absence of that optional validation dependency is
reported as `SKIPPED`; it is never rewritten as `PASS`. File-producing CLI
commands emit explicit UTF-8 bytes with one LF; the regression suite simulates
Windows text newline translation and redirected ASCII stdio.

## C# boundary

The C# source is self-contained and has no `UnityEngine` or
`Marcbeacve.TevLnu.Core` dependency. Earlier isolated .NET attempts stopped
inside SDK/NuGet path initialization before the compiler was reached:

```text
HOLD_ENVIRONMENT
NuGet.targets(782,5): Value cannot be null. (Parameter 'path1')
```

This is neither a C# PASS nor evidence of a C# source defect. Promotion of the
C# runtime remains blocked until a normal local .NET build succeeds and C#
reproduces the canonical vectors and all four shared receipts byte for byte.

Evidence:

```text
evidence/reference-v0.2/csharp-build-attempt.json
```

## Local commands

```powershell
python .\RUN_PORTABLE_CONFORMANCE.py

dotnet build .\runtimes\csharp\TevScript.Core\TevScript.Core.csproj

dotnet run `
  --project .\runtimes\csharp\TevScript.Core.Smoke `
  -- .\examples\Player.tevs.ir.json
```

No GitHub Action is authoritative or required.
