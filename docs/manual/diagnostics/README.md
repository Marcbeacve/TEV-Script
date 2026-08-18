# Referencia de diagnósticos

Los errores de usuario de TEVScript se identifican por **códigos estructurados**, no por parsing del texto humano del mensaje.

Para la superficie actual Total-Core 3.1, esta referencia separa los códigos por fase:

- [`source.md`](source.md) — parsing, composición de fuente, unidades V4 e inputs externos (`TEVS_V31_SOURCE_*`).
- `program-ir.md` — construcción y validación de Program IR V5 (`TEVS_V31_TOTAL_*`).
- `runtime.md` — checkpoints, quanta, proof admissions y ejecución (`TEVS_V31_RUNTIME_*`).
- `release-tooling.md` — identidad V31 de release/tooling cuando corresponda.

Las páginas `program-ir.md`, `runtime.md` y `release-tooling.md` se completan desde el inventario AST exacto antes de cerrar `DIAGNOSTIC_COVERAGE`.

## Forma de un diagnóstico de CLI

Los comandos `check` y `compile` representan un `TevScriptError` como un objeto de `stderr` con schema:

```text
TEV_SCRIPT_V31_DIAGNOSTIC_V1
```

La información útil está bajo:

```text
diagnostic.code
diagnostic.message
diagnostic.span
diagnostic.hint
```

`code` es la clave de referencia estable de esta documentación. `message` puede aportar contexto humano adicional, pero no debe usarse como identificador de programa.

## Ejemplos negativos ejecutables

Un ejemplo de error no se considera evidencia documental sólo porque «parece fallar». Cada caso negativo contiene:

```text
main.tevs
case.json
```

y el Markdown declara el código esperado con:

```text
<!-- tevdoc-expect-diagnostic: TEVS_EXACT_CODE -->
```

El validador exige que la CLI pública falle y produzca exactamente ese código. Si la fuente empieza a pasar o devuelve otro diagnóstico, la documentación falla.

## Alcance

El gate actual inventaría todos los literales `TEVS_V31_*` presentes en `tev_script/**/*.py`. Las familias compatibles V4/V3/V1 que pueden propagarse desde una unidad hija se documentarán como capa de compatibilidad explícita; no se confunden con el namespace V31 actual.
