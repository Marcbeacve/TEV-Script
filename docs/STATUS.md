# Status

```text
VERSION=0.2.0-preview
LANGUAGE_STABLE=NO

SIGNED_UPDATE_GATE5C=PASS_CERTIFIED
ANTI_REPLAY_GATE5D=PASS_CERTIFIED_WITH_DURABLE_STATE_BOUNDARY
REMOTE_TRANSPORT_GATE5E=PASS_CERTIFIED_LOOPBACK_HTTP_IL2CPP
UNITY_WEB_WASM_GATE6A=PASS_CERTIFIED
PURE_CORE_BROWSER_WASM_GATE6B=PASS_CERTIFIED_AOT
PURE_CORE_WASI_GATE6C=PASS_CERTIFIED_WASMTIME

SIGNED_WASM_UPDATE_GATE6D_BROWSER=PASS_OBSERVED_LOCAL_PRECOMMIT
SIGNED_WASM_UPDATE_GATE6D_WASI=PASS_OBSERVED_LOCAL_PRECOMMIT
GATE6D_UPDATE_AUTHORITY=SAME_TEV_AUTHORITY
GATE6D_MANAGED_ES256=PASS
GATE6D_BROWSER_WEBCRYPTO_ORACLE=PASS
GATE6D_BROWSER_RESTART_RESTORE=PASS_LOCALSTORAGE
GATE6D_WASI_TWO_PROCESS_RESTORE=PASS_FILE_STORE
GATE6D_REPLAY_AFTER_RESTORE=FAIL_CLOSED_PASS
GATE6D_STORE_FAILURE_RUNTIME_ROLLBACK=PASS
GATE6D_CORE_PRODUCT_CHANGES=0
GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL

DISTRIBUTED_DETERMINISM=PENDING_AFTER_GATE6D
STABLE_RELEASE=NO
```

Gate-6D is observed PASS on the local precommit candidate in both a real browser and Wasmtime. It reuses the same signed transactional TEV authority certified in Gates 5C/5D. The only shared product addition is a host-independent managed ES256 verifier in the Update layer, mirrored byte-identically for C# and Unity; TEV Core changes are zero.

Precommit campaign evidence SHA-256:

`024fdd1125afc8ab4b6300e042a341415738650a9ce845868757ae32bb3d558e`

The browser durable witness is scoped to persistent `localStorage` on the same loopback origin/profile across a true process restart. The WASI durable witness is scoped to a file store shared by two Wasmtime processes. Hostile rollback-resistant storage, production signing-key provisioning, public WAN/TLS/DNS/CDN, distributed deterministic replay/lockstep and stable release are not claimed here. Exact Gate-6D commit authority requires the post-commit clean-tree rerun and external receipt.
