# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Python / JavaScript / C# conformance:             PASS CERTIFICADO
Unity Editor / PlayMode / Mono / IL2CPP:          PASS CERTIFICADO
Gate-5A transactional program swap:               PASS CERTIFICADO
Gate-5B transactional swap inside IL2CPP/AOT:     PASS CERTIFICADO
Gate-5C signed canonical update package:          PASS CERTIFICADO
Gate-5D durable anti-replay authority:             PASS CERTIFICADO WITH BOUNDARY
Gate-5E remote transport inside IL2CPP:            PASS CERTIFICADO LOOPBACK_HTTP

Gate-6A Unity Web -> IL2CPP/WASM -> browser:       PASS OBSERVED LOCAL PRECOMMIT
Gate-6B pure TEV Core -> browser-wasm:             PASS OBSERVED LOCAL PRECOMMIT
Gate-6C pure TEV Core -> WASI/Wasmtime:            PASS OBSERVED LOCAL PRECOMMIT
Gate-6D signed transactional update on WASM:      NOT IN SCOPE

Browser authority:                                LOOPBACK_HTTP_WITNESS
Gate-6B AOT:                                      PASS REQUESTED AND EXECUTED
Gate-6C Wasmtime:                                 47.0.3
Gate-6C WASI HTTP:                                ENABLED FOR LINKAGE ONLY
Core SHA-256 provider:                            TEV MANAGED HOST INDEPENDENT
Core product changes:                             2 PHYSICAL / 1 LOGICAL
Stable release:                                   NO
```

## Log de cambios

- Gate-6A proves TEV Script through Unity WebGL, IL2CPP/WebAssembly and a real Chromium browser.
- Gate-6A browser authority is a nonce-bound loopback HTTP witness; `dump-dom`, browser stdout and CDP WebSocket are not authorities.
- Gate-6B proves the pure C# TEV Core in `browser-wasm`, including requested AOT and real browser execution.
- Gate-6C proves the pure C# TEV Core under .NET WASI and Wasmtime using the SDK-generated non-single-file execution contract.
- Gate-6C enables Wasmtime `-S http` only to satisfy .NET runtime linkage; this is not a TEV semantic capability.
- Real WASI execution falsified the previous host crypto assumption: `SHA256.Create()` raised `PlatformNotSupportedException`.
- The canonical TEV SHA-256 path now uses a managed host-independent implementation mirrored byte-identically between C# Core and Unity Core.
- The SHA-256 replacement preserved the canonical hash semantics under the existing C# conformance vectors and cross-runtime byte parity.
- No signed-update crypto provider was changed; Gate-6D remains out of scope.

## Hipótesis falsable

The same TEV Core semantics, canonical JSON identity and deterministic state transition behavior can execute unchanged across Unity WebGL/browser, pure .NET browser-wasm and .NET WASI/Wasmtime when host-specific execution and observation mechanisms remain outside the semantic Core. Canonical SHA-256 identity must be independent of host cryptography-provider availability.

## Tareas

1. Create one exact local commit for Gates 6A/6B/6C and the justified portable SHA-256 Core change.
2. Repeat Gates 6A/6B/6C from that exact clean commit and bind an external certification receipt to HEAD/TREE.
3. Only after the clean rerun passes, publish the certified branch by normal push and independently verify it on GitHub.
4. Fast-forward the PR head branch only after certified publication; keep PR #1 Draft/Open/Unmerged.
5. Open Gate-6D separately: signed transactional update on WASM with host-specific crypto provider boundaries.

## Verificación precommit

```text
GATE6A=PASS_OBSERVED_LOCAL_PRECOMMIT_REAL_BROWSER
GATE6B=PASS_OBSERVED_LOCAL_PRECOMMIT_PURE_CORE_BROWSER_WASM
GATE6B_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED
GATE6C=PASS_OBSERVED_LOCAL_PRECOMMIT_PURE_CORE_WASI
GATE6C_WASMTIME_EXECUTION=PASS
GATE6D=NOT_IN_SCOPE
CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL
CORE_SHA256_PROVIDER=TEV_MANAGED_HOST_INDEPENDENT
PRECOMMIT_EVIDENCE_SHA256=08a8c949ffb4e8991030a5684dec0523d2691adc9b9fcc9d76e0642109bc09bf
STABLE_RELEASE=NO
```

This committed state records Gates 6A/6B/6C as observed precommit. Exact certification authority is established only by the subsequent clean-tree rerun on this commit and its ignored external receipt.
