# Referencia del lenguaje TEVScript

Esta sección es la referencia de consulta de la superficie de fuente que interviene en la plataforma TEVScript 3.1. No sustituye a las especificaciones normativas: resume sus contratos de forma orientada al programador y señala siempre la autoridad técnica.

## Clasificación de superficies

Cada construcción se clasifica en uno de estos estados:

- **CURRENT** — forma propia del frontend `3.1.0 / total_core`.
- **INHERITED_COMPATIBILITY** — sintaxis V1/V2/V3 que conserva su semántica original y que 3.1 integra sin reinterpretar.
- **INTERNAL** — IR, schema, helper o detalle de runtime; no es sintaxis que deba escribir el usuario.
- **REJECTED** — forma no admitida por el frontend/perfil indicado.

## No existe un único parser universal

La plataforma actual compone varias generaciones, pero no las mezcla léxicamente:

```text
root Total-Core 3.1
    process/fact/field/transform/labels/unit/invoke_v4
    comentarios de línea raíz: # al inicio lógico de línea

unidad V2 pure/recursive/effects
    script/module/fn/record/state/action/...
    comentarios V2: //
```

Una unidad declarada `unit Calc profile pure` sigue siendo fuente V2 `2.0.0`; no se escribe con el header `process ... 3.1.0`.

## Ruta actual recomendada

```text
process 3.1 Total-Core
    ↓ contiene/referencia
unidades V4
    ↑ compiladas desde
fuente V2 compatible
```

La ruta V3 `3.0.0 semantic_process` permanece compatible/histórica y aporta la base de facts, Fields, Transformations y control que el frontend Total-Core reutiliza.

## Índice

- [`lexical.md`](lexical.md) — UTF-8, comentarios, identificadores, separadores y versiones.
- [`values-and-types.md`](values-and-types.md) — tipos portables, records, variants y colecciones.
- [`expressions.md`](expressions.md) — expresiones puras, operadores, llamadas, match, folds y tareas.
- [`declarations-and-functions.md`](declarations-and-functions.md) — declaraciones, funciones, genéricos, recursión y entries.
- [`control-and-bounds.md`](control-and-bounds.md) — control finito, recursion contracts, quanta y PC.
- [`state-events-effects.md`](state-events-effects.md) — estado V2, observations, commands y frontera física.
- [`modules.md`](modules.md) — módulos/linking y unidades V4.
- [`semantic-process.md`](semantic-process.md) — facts, Field, transform y labels V3/3.1.
- [`field-transformation-apply.md`](field-transformation-apply.md) — semántica operacional central.
- [`total-core.md`](total-core.md) — gramática/contrato root 3.1.
- [`proof-admissions.md`](proof-admissions.md) — evidencia externa requerida por transformations proof-open.
- [`source-to-ir.md`](source-to-ir.md) — qué se canonicaliza y qué artefacto consume runtime.

## Regla de autoridad

Cuando esta referencia y una especificación normativa discrepan, la especificación es la autoridad y la discrepancia es un defecto documental. Las implementaciones Python/JavaScript/C# son testigos de conformidad, no una licencia para redefinir la gramática.

## Versiones relevantes

```text
package actual                         3.1.2
lenguaje Total-Core actual            3.1.0
perfil de fuente actual               total_core
semantic process compatible           3.0.0
unidades de fuente V2 compatibles     2.0.0
Program IR raíz actual                V5 Total-Core
Program IR de unidades                V4
```

Consulta `docs/manual/versions/` para separar package/language/profile/IR/runtime/checkpoint.

## Autoridad primaria

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `spec/TEV_SCRIPT_VERSION_MATRIX.json`
