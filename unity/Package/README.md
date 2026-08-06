# TEV Script Unity Host — Gate 1

This package is the Unity host surface for TEV Script V0.2.

Gate 1 deliberately proves only that Unity 6000.3 can compile and execute the
same certified `TevScript.Core` implementation and reproduce the four canonical
conformance receipts byte-for-byte. It does not yet certify Unity physics,
Animator/Input bindings, Mono player builds, or IL2CPP.

The files under `Runtime/Core` are generated as byte-identical mirrors of
`runtimes/csharp/TevScript.Core`. `unity/VALIDATE_UNITY_PACKAGE.py` rejects any
drift between them.
