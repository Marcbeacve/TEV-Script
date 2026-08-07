# Unity Adapter Contract V2

Unity is a C# host of the portable runtime, not the language definition.

Recommended assemblies:

```text
Marcbeacve.TevScript.Core       no UnityEngine dependency
Marcbeacve.TevScript.Unity      Unity capability providers and behaviour
Marcbeacve.TevScript.Editor     .tevs importer and diagnostics
```

Minimum portable bindings:

```text
input.move2d
motion.move2d
animation.play
time.delta
debug.log
```

`motion.move2d` can be implemented by separate providers:

```text
TransformMotion2D
Rigidbody2DMotion
CharacterControllerMotion
```

The selected provider is explicit in composition/Inspector. The runtime must never silently choose a physics authority when more than one compatible provider is present.

Exact `Rat` values cross into Unity floats only at the physical capability boundary. `float -> Rat` records the exact IEEE-754 value observed by Unity. `Rat -> float` records the produced float bits, the exact rational represented by those bits, and the exact rounding error. Non-finite float values fail closed. These conversions are adapter evidence; they are not part of portable language arithmetic.

The `.tevs` importer runs the compiler only in Editor, stores the V2 IR as an asset, and maps diagnostics back through source spans. Python is not included in Mono or IL2CPP builds.

## Gate status

Gate Unity-1 certifies host neutrality of the C# Core. The package `com.marcbeacve.tev-script@0.2.0-preview.1` contains nine Core C# source files that remain byte-identical to `runtimes/csharp/TevScript.Core`. Unity Editor 6000.3.10f1 compiled and executed those sources and reproduced all four authoritative conformance receipts without observed semantic drift.

Gate Unity-2 exercises the capability ABI in Unity PlayMode while leaving the Core unchanged. Its observed campaign validates explicit providers for `input.move2d`, Transform-backed `motion.move2d`, an explicit Unity animation-state sink, `time.delta`, and `debug.log`, plus the audited `Rat`/float boundary and non-finite fail-closed behavior. Gate Unity-1 is re-run from its exact certified commit in an isolated clone before Gate Unity-2.

Gate Unity-2 does **not** certify a physical Input System device, a real Animator Controller, Mono Player or IL2CPP. Those remain separate falsifiable gates.
