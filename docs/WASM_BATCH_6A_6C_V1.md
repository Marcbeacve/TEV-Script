# WASM Batch 6A→6C V1 — V20 harness authority

Base authority: GitHub commit `966f87c43a5a2c9ba5336ae3a313515832dd8498`,
tree `62e1d86838adc191963686acd0f15f62ca4af187`.

This batch changes exactly 15 repository paths and makes zero product changes
to `TevScript.Core`.

## Gate-6A — Unity Web → IL2CPP/WebAssembly → real Chromium

Unity builds WebGL with compression disabled. The generated page is
instrumented only as a certification harness. The TEV `.jslib` still exposes
its internal DOM state, but external PASS/FAIL authority is now a one-shot
loopback HTTP witness bound to a fresh 128-bit nonce.

Before Unity runs, a separate page executes `canvas.getContext("webgl2")` in
real headless Chromium with explicit SwANGLE/SwiftShader flags. Only the true
WebGL2 branch may emit `gate6a-webgl2-probe / PASS / WEBGL2_CONTEXT_PASS`.

The Unity page emits `gate6a / PASS / TEV_JSLIB` only after the existing
`data-tev-gate6a=PASS` JSLib terminal state. Loader rejection, window errors,
unhandled rejections and alerts emit explicit FAIL witnesses.

## Gate-6B — pure TEV Core → browser-wasm → real Chromium

.NET publishes to an explicit external directory. `wwwroot` is the static web
root and runtime `dotnet*.js` discovery/rebinding remains temporary output
adaptation only. `main.mjs` emits a nonce-bound `gate6b` witness only on the
terminal Browser-WASM PASS/FAIL path. AOT remains explicitly requested.

## Browser witness authority

`HEADLESS_BROWSER_AUTHORITY=LOOPBACK_HTTP_WITNESS`.

For every browser gate the runner creates a new random 128-bit token and starts
an isolated local static server configured with exactly one expected gate and
one expected token. The page receives the token only through
`?tev_witness_token=<nonce>` and sends:

`GET /__tev_witness?gate=<gate>&status=PASS|FAIL&token=<nonce>&detail=<detail>`

The server validates gate, token and status, writes one JSONL receipt, flushes
it and calls `os.fsync`. A wrong nonce is ignored. After the first valid
receipt, token reuse is ignored. The PowerShell authority independently
revalidates schema, exact gate, exact token and status. Explicit FAIL aborts;
absence of a valid witness times out. Chrome stdout, launcher PID, `--dump-dom`
and CDP/WebSocket are not evidence authorities.

The runner includes a local witness-server contract test for wrong nonce,
first-use persistence, nonce reuse, explicit FAIL and missing-witness timeout.

## Gate-6C — pure TEV Core → WASI → Wasmtime

The .NET WASI pack determines the required wasi-sdk version from
`_ExpectedWasiSdkVersion` in `WasiApp.targets`; the SDK `VERSION` file is
checked with equivalent prefix semantics. The non-single-file .NET-generated
`run-wasmtime.sh` contract is required. R3 does not assume that helper is copied
to the custom `PublishDir`: .NET 10.0.10 writes it to `$(WasmAppDir)` (default
`$(OutputPath)/AppBundle`). The runner records the current publish boundary,
locates a fresh helper under the WASI project's `bin/**/AppBundle`, verifies the
contract, then executes from the publish working directory as:

`wasmtime run -S http --dir . dotnet.wasm TevScript.WasiGate`

`-S http` satisfies the .NET host linkage only; it is not a TEV semantic
capability. `Program.cs` is unchanged by V20.

## Boundary

Gate-6D signed transactional update on WASM is not in this batch. This batch
also does not claim stable release, public WAN/TLS/DNS/CDN, production key
provisioning, hostile rollback resistance or distributed lockstep.

The browser launcher redacts the nonce from logs. Obsolete long-held HTTP
resources are not part of V20; browser completion is witnessed only by the
nonce-bound terminal receipt.

## R4 — host-independent canonical SHA-256

Gate-6C R3 reached real Wasmtime execution and emitted `GATE6C_WASI_ACTIVE=PASS`,
then failed inside `TevJson.Hash` because `.NET 10 WASI` threw
`PlatformNotSupportedException` from `SHA256.Create()`. This is evidence of a
real Core portability defect rather than a harness defect.

R4 therefore changes one logical Core source in its two required mirrors:

- `runtimes/csharp/TevScript.Core/TevScriptJson.cs`
- `unity/Package/Runtime/Core/TevScriptJson.cs`

The mirrors remain byte-identical. `TevJson.Sha256` now uses a deterministic
managed SHA-256 implementation and no longer imports
`System.Security.Cryptography`. Before any WASM gate, the existing C#
conformance runner must re-prove all 12 canonical vectors plus
Python/JavaScript/C# byte parity. This change affects canonical hashing only;
signed-update ES256 providers are unchanged.

R4 repository boundary:

`EXPECTED_REPO_CHANGES=17`

`CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL`
