# Validation

## Current certified surface

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CANONICAL_JSON_VECTORS=PASS
STRICT_JSON_INPUT_BOUNDARY=PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_CORE_BUILD=PASS_OBSERVED_WINDOWS_DOTNET_10_0_302
CSHARP_GATE1_SMOKE=PASS
CSHARP_CANONICAL_VECTORS=12 PASS
CSHARP_STRICT_JSON_BOUNDARY=PASS
CSHARP_STRICT_UTF8_BOUNDARY=PASS
CSHARP_IR_NEGATIVE_CAMPAIGN=PASS
CSHARP_MISSING_CAPABILITY_FAIL_CLOSED=PASS
CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
POWERSHELL_MATERIALIZER_STATIC_STRUCTURE=PASS
```

Authoritative receipt hashes remain:

```text
PLAYER_RECEIPT_HASH=b275ccc6530ad84c0f96320ba1c8893b401638a926a99a78479d99fbd3c4aba5
MATRIX_RECEIPT_HASH=70df629159b6088aa3807deea217d4cdb06f28a41042aac1f6ebff6332179500
PLAYER_IDLE_RECEIPT_HASH=647d3211f7411b88c155d658ba4c9494482378cde75c9f427dc4e38475acd17c
EVENT_CHAIN_RECEIPT_HASH=5fcbd07512192ec298ff18bc313c71418e079e04d303aa3514a49ab91462371d
```

## C# conformance evidence

Observed on Windows x64 with .NET SDK 10.0.302 / `Microsoft.NETCore.App
10.0.10`. `TevScript.Core` targets `netstandard2.1`; the smoke and conformance
hosts target `net8.0` with `RollForward=Major` so newer installed runtimes can
execute the test hosts.

C# consumes the same `TEV_SCRIPT_CONFORMANCE_SCENARIO_V1` fixtures as the other
runtimes and produces the exact same canonical bytes for all four receipts. It
also passes the canonical-vector and negative-boundary campaign.

Evidence:

```text
evidence/reference-v0.2/csharp-conformance-windows-dotnet10.json
```

## JSON Schema continuity

`RUN_PORTABLE_CONFORMANCE.py` uses the optional external `jsonschema` package
when available. The observed Windows C# run reported
`JSON_SCHEMA_VALIDATION=SKIPPED_DEPENDENCY_UNAVAILABLE`; that is not rewritten
as PASS. Gate C#-2 changed no schema or authoritative scenario/receipt file, and
the three schema SHA-256 values are identical to the V7 surface that already
passed Draft 2020-12 validation. The versioned full C# gate checks those hashes
before accepting this continuity.

## Commands

```powershell
python .\RUN_PORTABLE_CONFORMANCE.py

pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1
```

For an exact committed candidate, rerun with:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1 `
  -RequireClean
```

No GitHub Action is authoritative or required.

## TEV_SCRIPT_LANGUAGE_COMPLETENESS_V1

Language-closure evidence is stored at `evidence/reference-v0.2/language-completeness-v1-windows-dotnet10.json`. The dynamic language regression ran once. Gates 5, 6 and 7 were not dynamically rerun. Functional payload SHA-256 identity: `e7af8fbe431507d52981600bef9721960a44dcccba7d97dd6ce6a79bcd413eef`. Stable release remains NO.
