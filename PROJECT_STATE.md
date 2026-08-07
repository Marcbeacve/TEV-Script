# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Python / JavaScript / C# conformance:      PASS CERTIFICADO
Unity Editor host/Core parity:             PASS CERTIFICADO
Unity PlayMode capability ABI:             PASS CERTIFICADO
Unity Mono Player Windows x64:             PASS CERTIFICADO
Unity IL2CPP Player Windows x64:           PASS CERTIFICADO
Gate-5A transactional program swap:        PASS CERTIFICADO
Gate-5B swap inside IL2CPP/AOT Player:     PASS OBSERVED LOCAL PRECOMMIT
Gate-5B old behavior witness:              PASS
Gate-5B updated behavior witness:          PASS
Gate-5B compatible state migration:        PASS
Gate-5B additive state initialization:     PASS
Gate-5B capability ceiling:                EXPLICIT PASS
Gate-5B rollback exact runtime:            PASS
Gate-5B rollback behavior restored:        PASS
Gate-5B stale-plan rejection:              FAIL CLOSED PASS
Gate-5B product/Core changes:              0
Gate-5B dynamic code:                      ABSENT PASS
Gate-5B network transport:                 NOT IN SCOPE
Gate-5B signature authority:               NOT IN SCOPE
Gate-5B WASM:                              NOT IN SCOPE
Stable release:                            NO
```

## Log de cambios

- Gate-5B reutiliza sin cambios el supervisor transaccional certificado en Gate-5A.
- El harness se ejecuta dentro de un Windows x64 Player construido con IL2CPP/AOT.
- El comportamiento inicial ejecuta `damage(10)` y lleva `health` de 100 a 90.
- El candidato conserva el estado vivo, añade un estado nuevo y sustituye el comportamiento de `damage` por un no-op.
- Tras el commit transaccional, `health=90` permanece y un nuevo `damage(10)` deja el valor en 90, demostrando que el comportamiento nuevo está activo.
- El rollback restaura el objeto runtime anterior exacto; otro `damage(10)` lleva `health` de 90 a 80, demostrando que vuelve también la semántica anterior.
- State removal, capability escalation, program-id drift, plan reuse y stale plan fallan cerrados.
- `GameAssembly.dll` y `global-metadata.dat` están presentes y `MonoBleedingEdge` está ausente.
- Gate-4 y Gate-5A se reejecutan como regresiones inferiores.
- Gate-5B no modifica ningún archivo productivo del Core ni del adapter.

## Hipótesis falsable

El reemplazo transaccional Gate-5A no depende de JIT, reflection ni compilación
dinámica: el mismo mecanismo puede ejecutar un cambio real de comportamiento,
migrar estado y restaurar el comportamiento anterior dentro de un Player
IL2CPP/AOT nativo.

## Tareas

1. Certificar Gate-5B sobre un commit exacto y árbol Git limpio.
2. Ejecutar Batch Hot Update 5C→5E:
   firma de paquete → anti-replay/versionado → transporte remoto.
3. Abrir la campaña WASM una vez cerrado el batch hot-update.
4. Mantener el Core matemático y el orden semántico preparados para la futura
   frontera de determinismo distribuido.

## Verificación

```text
GATE5B_GATE4_REGRESSION=PASS
GATE5B_GATE5A_REGRESSION=PASS
GATE5B_IL2CPP_BUILD=PASS
GATE5B_IL2CPP_EXECUTION=PASS
GATE5B_BACKEND=IL2CPP
GATE5B_AOT=PASS
GATE5B_GAMEASSEMBLY=PASS
GATE5B_GLOBAL_METADATA=PASS
GATE5B_MONO_RUNTIME=ABSENT_PASS
GATE5B_TRANSACTIONAL_SWAP=PASS_INSIDE_IL2CPP
GATE5B_STATE_MIGRATION=EXACT_EXISTING_TYPES_PASS
GATE5B_UPDATED_BEHAVIOR=PASS
GATE5B_ADDITIVE_STATE=PASS
GATE5B_CAPABILITY_CEILING=EXPLICIT_PASS
GATE5B_ROLLBACK=EXACT_PREVIOUS_RUNTIME_PASS
GATE5B_ROLLBACK_BEHAVIOR=RESTORED_PASS
GATE5B_STALE_PLAN=FAIL_CLOSED_PASS
GATE5B_DYNAMIC_CODE=ABSENT_PASS
GATE5B_PRECOMMIT_PLAYER_EXE_SHA256=c05ef2b9ae780cac8fc66d81eef3179cb52b49694235b5ba38c863b26b22f180
GATE5B_PRECOMMIT_GAMEASSEMBLY_SHA256=4c12a147cbb8a9c0955369a0cbe657a35ca6721e7a28d9c5af6ab5630ac7dc92
GATE5B_PRECOMMIT_GLOBAL_METADATA_SHA256=c275fb10db88810f7fcc0eb2f96fce2ed6d0f8a260a0f4747944845170277266
GATE5B_PRECOMMIT_BUILD_EVIDENCE_SHA256=e0711c90633579e175f6caa3d3c15d9780c13295cbc3d8a690d6df6c38f519c9
GATE5B_PRECOMMIT_PLAYER_EVIDENCE_SHA256=6a0fb8a91f201296d085b97798135f12efb3082feb9d412e040df1398b25069c
STABLE_RELEASE=NO
```

This committed state records Gate-5B as a precommit observation only. Exact
Gate-5B commit authority is established by the subsequent clean-tree rerun and
external certification receipt.
