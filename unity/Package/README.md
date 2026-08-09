# TEV Script Unity Host — Gates 1–4

This package is the Unity host surface for TEV Script V0.2. Unity is a host, not the language authority.

Gate 1 certifies that Unity 6000.3 can compile and execute the same `TevScript.Core` implementation and reproduce the four canonical conformance receipts byte-for-byte. The files under `Runtime/Core` remain byte-identical mirrors of `runtimes/csharp/TevScript.Core`.

Gate 2 adds the separate `Marcbeacve.TevScript.Unity` capability layer and certifies it in PlayMode with explicit input, Transform motion, an animation-state sink, `time.delta`, `debug.log`, and an audited `Rat`/IEEE-754 float conversion boundary. It does not modify `TevScript.Core`.

Gate 3 certifies that the same package can be built as a Windows x64 Player with the Mono backend and that the resulting Player process executes the TEV Script runtime/capabilities outside the Editor and exits successfully. The Gate-3 harness/build scripts live outside the product package under `unity/PlayerGates/Mono`.

Gate 4 observes the same runtime/capability surface in a Windows x64 IL2CPP/AOT Player. The gate explicitly requires `GameAssembly.dll` and IL2CPP metadata, rejects a Mono runtime layout, executes the built Player and requires the TEV runtime/capability witnesses before exit 0. Its harness/build scripts live outside the product package under `unity/PlayerGates/IL2CPP`.

Input System device bindings and Animator Controller bindings remain independent provider gates. Browser execution and stable release remain separate project boundaries.
