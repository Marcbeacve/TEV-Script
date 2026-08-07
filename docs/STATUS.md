# Status

```text
VERSION=0.2.0-preview
LANGUAGE_STABLE=NO

UNITY_IL2CPP_PLAYER=PASS_CERTIFIED
TRANSACTIONAL_PROGRAM_SWAP_GATE5A=PASS_CERTIFIED
IL2CPP_TRANSACTIONAL_SWAP_GATE5B=PASS_CERTIFIED
SIGNED_UPDATE_GATE5C=PASS_CERTIFIED
ANTI_REPLAY_GATE5D=PASS_CERTIFIED_WITH_DURABLE_STATE_BOUNDARY
REMOTE_TRANSPORT_GATE5E=PASS_CERTIFIED_LOOPBACK_HTTP_IL2CPP

UNITY_WEB_WASM_GATE6A=PASS_OBSERVED_LOCAL_PRECOMMIT_REAL_BROWSER
PURE_CORE_BROWSER_WASM_GATE6B=PASS_OBSERVED_LOCAL_PRECOMMIT
PURE_CORE_BROWSER_WASM_AOT=PASS_REQUESTED_AND_BROWSER_EXECUTED
PURE_CORE_WASI_GATE6C=PASS_OBSERVED_LOCAL_PRECOMMIT
WASMTIME_EXECUTION=PASS
WASMTIME_VERSION=47.0.3
WASI_HTTP=ENABLED_FOR_LINKAGE_ONLY

BROWSER_AUTHORITY=LOOPBACK_HTTP_WITNESS
CORE_SHA256_PROVIDER=TEV_MANAGED_HOST_INDEPENDENT
CORE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL

SIGNED_WASM_UPDATE_GATE6D=NOT_IN_SCOPE
DISTRIBUTED_DETERMINISM=PENDING_AFTER_WASM_UPDATE
STABLE_RELEASE=NO
```

Gates 6A/6B/6C are observed PASS on the local precommit candidate. Gate-6A uses a real browser and nonce-bound loopback HTTP witness. Gate-6B executes the pure TEV Core under browser-wasm with requested AOT. Gate-6C executes the pure TEV Core under .NET WASI and Wasmtime.

WASI exposed a real Core portability defect in the previous use of `SHA256.Create()`. The canonical hash implementation is now managed and host-independent while preserving the existing canonical vectors and cross-runtime byte identity. This change affects two mirrored physical files but one logical Core implementation.

Precommit campaign evidence SHA-256:

`08a8c949ffb4e8991030a5684dec0523d2691adc9b9fcc9d76e0642109bc09bf`

Gate-6D, stable release, public WAN/TLS/DNS/CDN, production signing-key provisioning, hostile rollback-resistant durable storage and distributed deterministic replay/lockstep are not claimed here. Exact Gates 6A/6B/6C commit authority requires the post-commit clean-tree rerun and external receipt.
