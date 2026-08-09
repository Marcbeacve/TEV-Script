# Gate-6D — signed transactional update on WebAssembly

Base authority: `3d0390d0071204410544a3989391283fd0b66bfa`.

## Hypothesis

The already-certified TEV signed-update authority can execute unchanged on
browser-wasm and WASI if signature verification is supplied by a synchronous,
host-independent ES256/P-256/SHA-256 verifier. Host storage remains behind
`ITevInstalledUpdateStore`.

## Product boundary

- `TevScript.Core`: **0 changes**.
- Existing `TevScript.Update` security providers: **0 changes**.
- New product capability: one managed verifier, mirrored byte-identically in
  C# Update and Unity Update (`2_PHYSICAL_1_LOGICAL`).
- No private signing key is added to product or gate code.
- The existing Gate-5C fixture tool remains the only test private-key scope.

## Browser proof

Two real browser executions share one origin/profile:

1. fresh: verify package, Prepare is non-authoritative, commit, replay reject,
   advance sequence, persist through localStorage;
2. restore: restore signed package in a new .NET/browser execution, reject
   replay after restore, advance epoch.

The browser's WebCrypto ECDSA/P-256/SHA-256 verification is an independent
oracle over the same P1363 64-byte signature. It is not TEV authority.

## WASI proof

Two Wasmtime processes share the same preopened publish directory:

1. fresh: signed update + replay rejection + durable file store;
2. restore: signed restore + replay rejection after restart + epoch advance.

The SDK-generated non-single-file run contract remains the execution contract.
`-S http` is enabled only for .NET WASI runtime linkage as established by Gate-6C.

## Negative boundaries

- tampered signed body: fail closed;
- wrong signing key: fail closed;
- key-authority mismatch: fail closed;
- algorithm substitution: fail closed;
- durable-store failure: runtime rollback pass;
- replay before and after restore: fail closed;
- private key in new product/gate surface: forbidden.

## Not claimed

- stable release;
- production signing-key provisioning/rotation;
- hostile rollback-resistant browser/WASI storage;
- public WAN/TLS/DNS/CDN transport;
- distributed deterministic replay/lockstep.

## Browser persistence hardening R2

The first Browser-WASM campaign observed `fresh=PASS` followed by `restore=FAIL`
after the harness force-killed Chromium 800 ms after the fresh witness. The
product verifier and WebCrypto oracle had already passed. R2 therefore changes
only the browser harness boundary: Chromium is launched with
`--enable-aggressive-domstorage-flushing`, the fresh phase receives an explicit
flush window, and shutdown is attempted without `/F` before force is allowed as
a fallback. The second process remains the authority for proving persistence.
A failed restore now emits a bounded diagnostic distinguishing a missing durable
record from TEV contract failures. No Core semantics change.
