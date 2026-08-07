# TEV Script Unity Host — Gates 1–3

This package is the Unity host surface for TEV Script V0.2. Unity is a host, not the language authority.

Gate 1 certifies that Unity 6000.3 can compile and execute the same `TevScript.Core` implementation and reproduce the four canonical conformance receipts byte-for-byte. The files under `Runtime/Core` remain byte-identical mirrors of `runtimes/csharp/TevScript.Core`.

Gate 2 adds the separate `Marcbeacve.TevScript.Unity` capability layer and certifies it in PlayMode with explicit input, Transform motion, an animation-state sink, `time.delta`, `debug.log`, and an audited `Rat`/IEEE-754 float conversion boundary. It does not modify `TevScript.Core`.

Gate 3 observes that the same package can be built as a Windows x64 Player with the Mono backend and that the resulting Player process executes the TEV Script runtime/capabilities outside the Editor and exits successfully. The Gate-3 harness/build scripts live outside the product package under `unity/PlayerGates/Mono`.

Input System device bindings, Animator Controller bindings and IL2CPP remain independent gates.
