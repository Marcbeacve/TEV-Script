# TEV Script Unity Host — Gates 1–2

This package is the Unity host surface for TEV Script V0.2. Unity is a host, not the language authority.

Gate 1 certifies that Unity 6000.3 can compile and execute the same `TevScript.Core` implementation and reproduce the four canonical conformance receipts byte-for-byte. The files under `Runtime/Core` are byte-identical mirrors of `runtimes/csharp/TevScript.Core`; `unity/VALIDATE_UNITY_PACKAGE.py` rejects any drift.

Gate 2 adds a separate `Marcbeacve.TevScript.Unity` capability layer and exercises it in PlayMode. It validates explicit `input.move2d`, Transform motion, an animation-state sink, `time.delta`, `debug.log`, and an audited `Rat`/IEEE-754 float conversion boundary. It does not modify `TevScript.Core`.

Gate 2 does not yet certify Input System device bindings, Animator Controller bindings, Mono Player builds or IL2CPP. Those remain independent host/provider gates.
