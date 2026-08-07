# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Decisión de autoridad multilenguaje:       CERRADA
Implementación completa del lenguaje:      NO, PREVIEW 0.2
IR portable V2:                            IMPLEMENTADO Y ESQUEMA ESTRICTO
Python/JavaScript/C# byte parity:          PASS, 4 ESCENARIOS
Unity Editor 6000.3 host/Core parity:      PASS CERTIFICADO
Unity PlayMode capability ABI:             PASS CERTIFICADO
Unity Mono Player Windows x64:             PASS CERTIFICADO
Unity IL2CPP Player Windows x64:            PASS CERTIFICADO
Gate-5A transactional program swap:        PASS OBSERVED LOCAL PRECOMMIT
Gate-5A state migration:                   EXACT EXISTING TYPES PASS
Gate-5A additive state:                    PASS
Gate-5A capability ceiling:                EXPLICIT PASS
Gate-5A rollback:                          EXACT PREVIOUS RUNTIME PASS
Gate-5A stale-plan rejection:              FAIL CLOSED PASS
Gate-5A network transport:                 NOT IN SCOPE
Gate-5A signature authority:               NOT IN SCOPE
Browser/WASM execution campaign:           PENDIENTE
Stable release:                            NO
```

## Log de cambios

- Gate Unity-4 está certificado en `39060bfc80bb0b7cc88515261d4f18d9c462a2b6`.
- Gate-5A mantiene `TevScriptRuntime` como runtime de programa fijo y añade un supervisor `TevScriptRuntimeHost`.
- `PrepareSwap` valida primero un `TEV_SCRIPT_PROGRAM_IR_V2`, continuidad de `program_id`, identidad de entidades, continuidad de estados y un ceiling explícito de capabilities.
- El runtime candidato se construye aisladamente y recibe un snapshot compatible antes de cualquier cambio de autoridad.
- `Commit` realiza el único cambio autoritativo: sustituye la referencia al runtime activo bajo lock.
- `RollbackLastCommit` recupera el objeto runtime anterior exacto.
- Los planes reutilizados o stale fallan cerrados.
- Gate-5A no incorpora red, firmas, anti-replay, WASM ni claims de políticas de stores.
- El Core C# y su mirror Unity permanecen byte-idénticos.

## Hipótesis falsable

Un host TEV puede sustituir transaccionalmente un programa IR V2 completo sin mutar
en caliente el motor de ejecución, preservando el estado compatible, sin ampliar
la autoridad de capabilities y con rollback exacto.

## Tareas

1. Certificar Gate-5A sobre un commit exacto y árbol Git limpio.
2. Probar el mismo swap dentro de un Player IL2CPP/AOT (Gate-5B).
3. Añadir paquete firmado y autoridad de clave (Gate-5C).
4. Añadir anti-replay/versionado monótono (Gate-5D).
5. Añadir transporte remoto (Gate-5E).
6. Certificar navegador/WASM como frontera separada.

## Verificación

```text
GATE5A_GATE_BINARY_VERSION=V4
GATE5A_PREPARE_NON_AUTHORITATIVE=PASS
GATE5A_COMMIT_ATOMIC_REFERENCE_SWAP=PASS
GATE5A_EXISTING_STATE_MIGRATION=PASS
GATE5A_ADDITIVE_STATE_INITIALIZATION=PASS
GATE5A_PLAN_REUSE_FAIL_CLOSED=PASS
GATE5A_STATE_REMOVAL_VALID_IR_REACHES_HOST=PASS
GATE5A_STATE_REMOVAL_FAIL_CLOSED=PASS
GATE5A_CAPABILITY_CEILING_FAIL_CLOSED=PASS
GATE5A_PROGRAM_ID_CONTINUITY_FAIL_CLOSED=PASS
GATE5A_ROLLBACK_EXACT_RUNTIME_RESTORE=PASS
GATE5A_STALE_PLAN_FAIL_CLOSED=PASS
GATE5A_TRANSACTION_BOUNDARY=PASS
GATE5A_DYNAMIC_CODE=ABSENT_PASS
GATE5A_NETWORK=NOT_IN_SCOPE
GATE5A_SIGNATURE_AUTHORITY=NOT_IN_SCOPE
GATE5A_WASM=NOT_IN_SCOPE
GATE5A_PRECOMMIT_EVIDENCE_SHA256=794297c539d4f9c2a891d7952cdea080b6f109617c8e1687d30cf7a8c28b6d8a
STABLE_RELEASE=NO
```

This committed state records the Gate-5A precommit observation. Exact Gate-5A
commit authority is established only by the subsequent clean-tree rerun and
external certification receipt.
