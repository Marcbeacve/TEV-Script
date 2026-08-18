# Diagnósticos V31 de release y tooling

Esta página documenta los **18 códigos V31** que no pertenecen al parser/Program IR/runtime: 9 guards de metadata de release, 8 errores de la CLI explícita `tev-script-v31` y 1 diagnóstico de proyecto del LSP.

## Metadata de release (`TEVS_V31_RELEASE_*`)

Estos códigos son guards de coherencia de `tev_script/release_metadata_v31.py`. Normalmente indican un defecto de packaging/gobernanza del checkout, no un error del programa `.tevs` del usuario.

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_RELEASE_LANGUAGE_VERSION` | `LANGUAGE_VERSION` deja de ser `3.1.0`. | Restablecer la identidad normativa; un cambio de lenguaje requiere proceso de versión propio. |
| `TEVS_V31_RELEASE_CANDIDATE_STATUS` | Un perfil `candidate` usa un status distinto de `IMPLEMENTATION_CANDIDATE_CERTIFICATION_REQUIRED`. | Alinear perfil/status según el contrato de release. |
| `TEVS_V31_RELEASE_CANDIDATE_AUTHORITY` | Un candidate pretende `STABLE`, publicación o merge authority. | Mantener esas autoridades falsas hasta el gate correspondiente. |
| `TEVS_V31_RELEASE_CANDIDATE_PARENT` | Un candidate lleva technical-parent evidence donde el contrato exige vacío. | No introducir evidencia de stable-request en el perfil candidate. |
| `TEVS_V31_RELEASE_STABLE_STATUS` | `stable_request` no usa `STABLE_ADMISSION_REQUESTED`. | Corregir el status exacto del request. |
| `TEVS_V31_RELEASE_STABLE_AUTHORITY` | El stable request no cumple `STABLE=true`, `PUBLICATION_AUTHORITY=false`, `MERGE_AUTHORITY=false`. | Alinear los flags; solicitar estabilidad no concede merge/publicación. |
| `TEVS_V31_RELEASE_PARENT_COMMIT` | `TECHNICAL_PARENT_COMMIT` no es SHA Git de 40 hex. | Ligar el commit técnico exacto. |
| `TEVS_V31_RELEASE_PARENT_RECEIPT` | `TECHNICAL_PARENT_RECEIPT_SHA256` no es SHA-256 de 64 hex. | Ligar el receipt técnico exacto. |
| `TEVS_V31_RELEASE_PROFILE` | `RELEASE_PROFILE` no es `candidate` ni `stable_request`. | Usar un perfil gobernado explícitamente. |

## CLI explícita V31 (`TEVS_V31_CLI_*`)

La CLI genérica `tev-script` delega `check/compile/run` a esta implementación. Estos códigos representan fallos de entrada/IO del tooling; cuando el fallo es un `TevScriptError` de lenguaje, la CLI conserva el código de lenguaje original.

| Código | Significado / trigger | Corrección |
|---|---|---|
| `TEVS_V31_CLI_SOURCE_UTF8` | La fuente principal o una unidad no puede decodificarse como UTF-8. | Guardar los `.tevs` como UTF-8 válido. |
| `TEVS_V31_CLI_UNIT_BINDING` | `--unit` no tiene forma `NAME=PATH`, tiene nombre vacío/duplicado o path vacío. | Usar un mapping único por unidad, p. ej. `--unit Calc=calc.tevs`. |
| `TEVS_V31_CLI_EFFECT_BINDING` | `--effect-input` no tiene forma válida o repite unidad. | Usar `--effect-input Effects=input.json` una vez por unidad. |
| `TEVS_V31_CLI_EFFECT_INPUT` | El JSON de effect input no es JSON válido o no es objeto. | Proporcionar un objeto JSON que satisfaga el contrato de la unidad `effects`. |
| `TEVS_V31_CLI_PROOF_ADMISSION` | El archivo de proof admission no es JSON válido, no es objeto o no valida como `VerifiedProofAdmissionV1`. | Generar/cargar una admission canónica verificada. |
| `TEVS_V31_CLI_PROGRAM_IR` | `run` no puede leer/parsear/validar el Program IR V5. | Ejecutar un artefacto producido por `compile` y no manipulado. |
| `TEVS_V31_CLI_CHECKPOINT` | No puede escribirse el checkpoint solicitado. | Corregir ruta/permisos/IO de `--checkpoint-output`; el fallo físico permanece separado del estado semántico. |
| `TEVS_V31_CLI_EPOCHS` | `--epochs` está fuera de `1..1_000_000`. | Usar un entero dentro del rango explícito. |

## LSP (`TEVS_V31_LSP_PROJECT`)

### `TEVS_V31_LSP_PROJECT`

**Fase:** validación de documento/proyecto por el servidor de lenguaje.

**Significado:** la composición de la fuente actual falla por una condición de proyecto que no llegó como `TevScriptError` estructurado; el LSP la representa como diagnóstico de proyecto en lugar de inventar un código de lenguaje más específico.

**Trigger:** por ejemplo, un `ValueError`, `OSError` o error JSON durante la resolución/compilación del proyecto del documento.

**Corrección:** revisar bindings de unidades/evidence, archivos referenciados e inputs JSON. Cuando existe un `TevScriptError` específico, el LSP devuelve su código real en vez de `TEVS_V31_LSP_PROJECT`.

## Frontera

Estos 18 códigos no deben mezclarse conceptualmente:

```text
RELEASE_*  → coherencia del paquete/release
CLI_*      → entrada/IO de la herramienta
LSP_*      → adaptación de diagnósticos al editor
```

Ninguno redefine las reglas de `TEVS_V31_SOURCE_*`, `TEVS_V31_TOTAL_*` o `TEVS_V31_RUNTIME_*`.
