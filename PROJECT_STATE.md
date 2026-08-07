# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Python / JavaScript / C# conformance:             PASS CERTIFICADO
Unity Editor / PlayMode / Mono / IL2CPP:          PASS CERTIFICADO
Gate-5A transactional program swap:               PASS CERTIFICADO
Gate-5B transactional swap inside IL2CPP/AOT:     PASS CERTIFICADO

Gate-5C signed canonical update package:          PASS OBSERVED LOCAL PRECOMMIT
Gate-5D durable anti-replay authority:             PASS OBSERVED LOCAL PRECOMMIT
Gate-5E remote transport inside IL2CPP:            PASS OBSERVED LOCAL PRECOMMIT

Gate-5C algorithm:                                ES256 / P-256 / SHA-256
Gate-5C signature format:                         IEEE-P1363 fixed 64-byte r||s
Gate-5C runtime private key:                      ABSENT PASS
Gate-5D durable restart restoration:              PASS
Gate-5D replay after restart:                     FAIL_CLOSED PASS
Gate-5D hostile store rollback:                   NOT IN SCOPE
Gate-5E transport:                                LOOPBACK HTTP
Gate-5E signature provider on Windows IL2CPP:     WINDOWS CNG PASS
Gate-5E network bytes authority:                  UNTRUSTED UNTIL VERIFIED PASS
Gate-5E public WAN:                               NOT PROBED
Browser/WASM:                                     PENDING
Stable release:                                   NO
```

## Log de cambios

- Gate-5C introduces a canonical signed full-program update package.
- The signed body includes channel, program identity, epoch, sequence,
  semantic hash, IR SHA-256 and the complete canonical TEV IR.
- Gate-5C uses ES256 (ECDSA P-256 + SHA-256) with a fixed 64-byte
  IEEE-P1363 `r || s` signature.
- Test private-key material is confined to the fixture tool; product/runtime
  code contains no private signing key.
- `ITevUpdateSignatureVerifier` separates update semantics from the physical
  cryptographic provider.
- .NET Gate-5C/5D uses the managed ECDSA provider.
- Windows IL2CPP Gate-5E uses the Windows CNG provider through
  `BCryptImportKeyPair` / `BCryptVerifySignature`.
- Gate-5D persists the accepted signed package plus monotonic epoch/sequence.
- Bootstrap, replay, old epoch, invalid epoch transition and stale update
  plans fail closed.
- If durable commit fails, the runtime update is rolled back.
- A fresh runtime can reconstruct and reverify the installed signed package
  from durable state.
- Gate-5E downloads bytes through UnityWebRequest. Network bytes acquire no
  authority before canonical parse, signature verification, anti-replay and
  transactional prepare/commit.
- Gate-5E rejects tampered packages, truncated packages, HTTP errors and replay.
- A second real IL2CPP Player restores the durable package, rejects its remote
  replay and accepts the next epoch.
- Unity Core source identity was refreshed to the actual 11-file Core surface.

## Hipótesis falsable

A TEV program update can be delivered as untrusted network data and become
authoritative only after deterministic package parsing, cryptographic
authentication, monotonic anti-replay validation and the already certified
transactional runtime swap, while remaining compatible with a real
Windows x64 IL2CPP/AOT Player.

## Tareas

1. Certify Gates 5C/5D/5E together on one exact clean Git commit.
2. Publish the certified batch by normal fast-forward only.
3. Open the WASM batch:
   Unity Web/browser → pure TEV Core WASM → WASI/serverless.
4. Preserve exact arithmetic, canonical receipts and deterministic event
   ordering for the later distributed-determinism campaign.

## Verificación precommit

```text
HOT_UPDATE_GATE5B_REGRESSION=PASS
GATE5C_SIGNED_PACKAGE=PASS
GATE5C_ALGORITHM=ES256_P256_SHA256
GATE5C_SIGNATURE_FORMAT=IEEE_P1363_FIXED_64
GATE5C_TEST_PRIVATE_KEY_RUNTIME=ABSENT_PASS

GATE5D_ANTI_REPLAY=DURABLE_STATE_PASS
GATE5D_RESTART_RESTORE=PASS
GATE5D_HOSTILE_STORE_ROLLBACK=NOT_IN_SCOPE

GATE5E_REMOTE_TRANSPORT=LOOPBACK_HTTP_PASS_INSIDE_IL2CPP
GATE5E_SIGNATURE_PROVIDER=WINDOWS_CNG_PASS
GATE5E_BACKEND=IL2CPP
GATE5E_AOT=PASS
GATE5E_NETWORK_BYTES=UNTRUSTED_UNTIL_VERIFIED_PASS
GATE5E_TAMPER_FAIL_CLOSED=PASS
GATE5E_TRUNCATION_FAIL_CLOSED=PASS
GATE5E_HTTP_ERROR_FAIL_CLOSED=PASS
GATE5E_REPLAY_AFTER_RESTART_FAIL_CLOSED=PASS
GATE5E_PUBLIC_WAN=NOT_PROBED

HOT_UPDATE_BATCH_PRECOMMIT_EVIDENCE_SHA256=
3c1f52e56c52117bcfb4ffd548afeb564e9dec16a68552a7ad73b6e2b6308f38

WASM=NOT_IN_SCOPE
STABLE_RELEASE=NO
```

This committed state records Gates 5C/5D/5E as observed precommit. Exact
certification authority is established by the subsequent clean-tree batch
rerun and its ignored external receipt.
