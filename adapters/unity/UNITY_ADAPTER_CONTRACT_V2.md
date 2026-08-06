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

The selected provider is explicit in the Inspector. The runtime must never
silently choose a physics authority when more than one compatible provider is
present.

Exact `Rat` values cross into Unity floats only at the physical capability
boundary. The adapter records or exposes that conversion; it is not part of the
portable language arithmetic.

The `.tevs` importer runs the compiler only in Editor, stores the V2 IR as an
asset, and maps diagnostics back through source spans. Python is not included in
Mono or IL2CPP builds.
