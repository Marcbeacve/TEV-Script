# TEV Script Core — C# runtime V0.2

This directory implements `TEV_SCRIPT_PROGRAM_IR_V2` without dependencies on
`UnityEngine`, `Marcbeacve.TevLnu.Core`, reflection, dynamic code, or source
interpretation.

```text
TevScript.Core.csproj                  netstandard2.1 library
../TevScript.Core.Smoke                net8.0 smoke host, RollForward=Major
../TevScript.Core.Conformance          net8.0 conformance host, RollForward=Major
```

Observed Windows/.NET 10 evidence:

```text
CSHARP_CORE_BUILD=PASS
CSHARP_GATE1_SMOKE=PASS
CSHARP_CANONICAL_VECTORS=12_PASS
CSHARP_IR_NEGATIVE_CAMPAIGN=PASS
CSHARP_PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_CONFORMANCE_SCENARIOS=4_PASS
```

Run the complete gate from the repository root:

```powershell
pwsh -NoProfile -ExecutionPolicy Bypass `
  -File .\RUN_TEV_SCRIPT_CSHARP_CONFORMANCE_V1.ps1
```

This makes C# a conforming runtime implementation, not the language authority.
The normative authority remains the grammar, IR, value model, ABI, canonical
profile and conformance protocol.
