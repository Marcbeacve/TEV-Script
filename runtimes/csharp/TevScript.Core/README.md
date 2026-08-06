# TEV Script Core — C# runtime candidate V0.2

This directory implements `TEV_SCRIPT_PROGRAM_IR_V2` without dependencies on
`UnityEngine`, `Marcbeacve.TevLnu.Core`, reflection, dynamic code, or source
interpretation.

```text
TevScript.Core.csproj       netstandard2.1 library
../TevScript.Core.Smoke     dependency-free net8.0 smoke executable
```

Build and smoke test:

```text
dotnet build runtimes/csharp/TevScript.Core/TevScript.Core.csproj
dotnet run --project runtimes/csharp/TevScript.Core.Smoke -- examples/Player.tevs.ir.json
```

The C# implementation remains non-conformant until it emits the exact shared
receipt `b275ccc6530ad84c0f96320ba1c8893b401638a926a99a78479d99fbd3c4aba5`.
