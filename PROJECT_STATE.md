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
Gate-6A Unity Web / browser-WASM:                  PASS CERTIFICADO
Gate-6B pure Core browser-WASM AOT:                PASS CERTIFICADO
Gate-6C pure Core WASI / Wasmtime:                 PASS CERTIFICADO

Gate-6D signed update / Browser:                   PASS OBSERVED LOCAL PRECOMMIT
Gate-6D signed update / WASI:                      PASS OBSERVED LOCAL PRECOMMIT
Gate-6D Core product changes:                     0
Gate-6D Update product changes:                   2 PHYSICAL / 1 LOGICAL
Gate-6D verifier:                                 MANAGED ES256 P-256 SHA-256
Browser durable store:                            localStorage + process restart
Browser independent crypto oracle:                WebCrypto PASS
WASI durable store:                               file store + two Wasmtime processes
Stable release:                                   NO
```

## Log de cambios

- Gate-6D reuses the exact `TevScriptUpdateAuthority` certified by Gates 5C/5D instead of introducing a WASM-specific update authority.
- A synchronous managed ES256/P-256/SHA-256 public-key verifier is added only to the Update layer; TEV Core remains byte-identical to the certified Gate-6A/6B/6C Core.
- The verifier has no private key, native cryptography dependency, `DllImport`, `ECDsa.Create()` or `SHA256.Create()` dependency.
- Browser-WASM verifies and commits signed packages, rejects signature negatives, rolls runtime state back when durable commit fails, persists the installed package through `localStorage`, and restores it after a real browser-process restart.
- Browser WebCrypto independently verifies the same fixed 64-byte IEEE-P1363 signature and is an oracle, not TEV authority.
- WASI/Wasmtime executes the same signed update authority with a file-backed durable store across two independent Wasmtime processes.
- Replay after restore fails closed and the next epoch transition succeeds in both the governed update semantics and the WASI campaign.
- Gate-5C/5D desktop signed-update semantics are rerun as a regression before the WASM campaign.
- R2/R3 browser persistence and diagnostic hardening changed harness behavior only; no Core semantics were changed.

## Hipótesis falsable

The signed transactional update authority certified on desktop/IL2CPP can execute unchanged under browser-WASM and WASI when signature verification and durable storage are supplied by host-portable Update-layer providers. A process restart must preserve monotonic anti-replay authority, and a failed durable commit must roll the runtime back to its prior program.

## Tareas

1. Create one exact local Gate-6D commit from the observed 12-file candidate plus closure metadata.
2. Repeat the full Gate-6D Browser + WASI campaign from that exact clean child commit and bind the external receipt to HEAD/TREE.
3. Publish only after the clean rerun succeeds; then fast-forward PR #1 while keeping it Draft/Open/Unmerged.
4. After Gate-6D certification, open the distributed deterministic replay/lockstep campaign as a separate frontier.

## Verificación precommit

```text
TEV_SCRIPT_WASM_SIGNED_UPDATE_GATE_6D=PASS
GATE6D_BROWSER=PASS
GATE6D_BROWSER_WEBCRYPTO_ORACLE=PASS
GATE6D_WASI=PASS
GATE6D_WASI_TWO_PROCESS_RESTORE=PASS
GATE6D_GATE5C_5D_REGRESSION=PASS
GATE6D_CORE_PRODUCT_CHANGES=0
GATE6D_UPDATE_PRODUCT_CHANGES=2_PHYSICAL_1_LOGICAL
PRECOMMIT_EVIDENCE_SHA256=024fdd1125afc8ab4b6300e042a341415738650a9ce845868757ae32bb3d558e
STABLE_RELEASE=NO
```

This committed state records Gate-6D as observed precommit. Exact Gate-6D certification authority is established only by the subsequent clean-tree rerun on this commit and its ignored external receipt.
