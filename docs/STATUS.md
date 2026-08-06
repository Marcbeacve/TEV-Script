# Status

```text
VERSION=0.2.0-preview
LANGUAGE_STABLE=NO
PYTHON_TESTS=29_PASS
JAVASCRIPT_TESTS=21_PASS
CANONICAL_JSON_VECTORS=PASS
STRICT_JSON_INPUT=PASS
CONFORMANCE_SCENARIOS=4_PASS
PYTHON_CONFORMANCE=PASS
JAVASCRIPT_ES2022_CONFORMANCE=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
CSHARP_SOURCE=IMPLEMENTED_SELF_CONTAINED
CSHARP_COMPILE=HOLD_TOOLCHAIN_NOT_AVAILABLE_IN_VALIDATION_ENVIRONMENT
CSHARP_BYTE_PARITY=PENDING
BROWSER_EXECUTION_CAMPAIGN=PENDING
UNITY_ADAPTER=PENDING
MONO_IL2CPP=PENDING
LOWERING_TO_TEV_CAUSAL=PENDING
LOWERING_TO_TEV_GENERAL=PENDING
```

The current evidence proves Python/JavaScript byte parity for
`player.basic.v1`, `matrix.full.v1`, `player.idle.v1`, and `event-chain.v1`. It also proves the canonical vectors, strict JSON input
boundary, and strict schema validation in the observed environment. C# source
is self-contained, but this package does not claim a successful C# compilation.
It does not certify browsers, Unity, Mono, IL2CPP, or a stable release.
