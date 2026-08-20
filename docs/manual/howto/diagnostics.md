# Cómo diagnosticar un error TEVScript

## 1. Conserva el código exacto

Los errores current usan familias `TEVS_V31_*`; compatibilidad V2/V3 puede emitir sus familias históricas.

No reduzcas el incidente a «compilación falló». Conserva:

```text
code
message
span, si existe
hint, si existe
fase/comando
```

## 2. CLI V31

Ante `TevScriptError`, la ruta versionada emite stderr JSON con forma:

```json
{
  "schema":"TEV_SCRIPT_V31_DIAGNOSTIC_V1",
  "status":"FAIL",
  "diagnostic":{
    "code":"TEVS_V31_SOURCE_VERSION",
    "message":"..."
  }
}
```

y retorna 2.

Errores host/IO se separan en `TEV_SCRIPT_V31_HOST_IO_ERROR_V1`; no los recodifiques como diagnóstico semántico si la causa es filesystem/Unicode del host.

## 3. Busca el código

Consulta:

```text
docs/manual/diagnostics/current-inventory.md
docs/manual/diagnostics/source.md
docs/manual/diagnostics/program-ir.md
docs/manual/diagnostics/runtime.md
docs/manual/diagnostics/release-tooling.md
```

El inventario current se valida automáticamente contra los literals de autoridad V31.

## 4. Identifica la fase

Prefijos útiles:

```text
TEVS_V31_SOURCE_*    frontend/source
TEVS_V31_TOTAL_*     Program IR V5 / estructura
TEVS_V31_RUNTIME_*   ejecución/checkpoint/continuation
TEVS_V31_CLI_*       binding/entrada CLI versionada
TEVS_V31_LSP_*       proyecto/editor
TEVS_V31_RELEASE_*   metadata de release
```

La corrección correcta depende de la fase.

## 5. Corrige la causa, no el hash

Ejemplo: `TEVS_V31_TOTAL_PROGRAM_HASH` significa que el mapping y su identidad no coinciden. No recalcules a mano el hash sobre un IR editado para «hacerlo pasar»; recompila desde la fuente/input correcto o identifica por qué cambió el artefacto.

## 6. Usa `check` antes de `compile`

```powershell
tev-script check .\main.tevs [bindings]
```

reduce ciclos porque valida/compila semánticamente sin escribir output.

## 7. Distingue source child/root

Si el error viene de una unidad V2, puede usar código `TEVS_V2_*` aunque el root sea 3.1. Eso no es una regresión de versionado: la unidad conserva su autoridad V2.

## 8. Diagnósticos de editor

El LSP convierte `TevScriptError` a `textDocument/publishDiagnostics`, usando UTF-16 positions. Sin span válido, publica posición 0:0 en vez de inventar un rango.

Errores de proyecto del LSP usan `TEVS_V31_LSP_PROJECT`.

## 9. Reproduce mínimo

Reduce el caso conservando:

- mismo header/profile;
- mismo binding que dispara el fallo;
- misma identidad/authority relevante;
- mismo expected diagnostic.

Un test negativo debe comprobar el **código**, no sólo «lanza alguna excepción» cuando el contrato exige estabilidad.

## 10. Si el código no está documentado

Eso es un fallo del sistema documental current. `DIAGNOSTIC_COVERAGE_V31.json` usa families wildcard por authority y el validator debe fallar si aparece un literal V31 nuevo que no está en la página de inventario.

## Ejemplos de causa rápida

```text
TEVS_V31_SOURCE_VERSION
  → root no declara 3.1.0

TEVS_V31_SOURCE_UNIT_SET
  → --unit no coincide con declarations

TEVS_V31_TOTAL_UNIT_SCHEMA
  → profile V5 y schema V4 no coinciden

TEVS_V31_TOTAL_PROOF_REQUIRED
  → Apply proof-open sin admission exacta

TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM
  → checkpoint de otro program_hash
```

## Referencia

- `docs/manual/diagnostics/`
- `tev_script/diagnostics.py`
- `tev_script/cli_v31.py`
- `tev_script/lsp_v31.py`
