# Diagnósticos

Los diagnósticos TEVScript son parte del contrato de fallo cerrado. Para automatización y tests debes conservar el **código**, no depender de que el texto humano del mensaje sea idéntico para siempre.

## Por dónde empezar

La referencia current autoauditable está en [`current-inventory.md`](current-inventory.md). `DIAGNOSTIC_COVERAGE_V31.json` liga cada familia a archivos de autoridad y usa descubrimiento wildcard: un literal `TEVS_V31_*` nuevo en una authority cubierta hace fallar el gate hasta aparecer en el inventario.

## Por fase

- [`source.md`](source.md) — parsing/normalización Total-Core y casos negativos de fuente.
- [`program-ir.md`](program-ir.md) — unidades, instructions, proof admissions, hashes y canonical ordering.
- [`runtime.md`](runtime.md) — checkpoint, continuation, proof use, bridges y quantum execution.
- [`release-tooling.md`](release-tooling.md) — metadata de release, CLI/LSP/tooling current.

Una unidad V2 child puede emitir `TEVS_V2_*`; eso no debe recodificarse artificialmente como V31. El error conserva la autoridad de la capa que lo detectó.

## Forma CLI V31

Un `TevScriptError` se proyecta como JSON de diagnóstico con `status = FAIL` y exit code 2. Los errores de host/IO se mantienen separados cuando no son fallos semánticos.

## Casos negativos ejecutables

`examples/docs/v31/diagnostics/` contiene inputs que deben fallar. Un `case.json` fija:

```text
expected_returncode = 2
expected_status = FAIL
expected_diagnostic_code = TEVS_...
```

Cuando una página muestra un caso negativo con `tevdoc-expect-diagnostic`, el closeout test exige que ese código coincida con su `case.json` canónico.

## Procedimiento de depuración

1. identifica el código exacto;
2. clasifica source / IR / runtime / CLI-LSP-release;
3. reproduce mínimo sin cambiar profile/version;
4. corrige la entrada o la capa que posee la regla;
5. no recalcules hashes a mano para hacer pasar un artefacto modificado;
6. añade/actualiza el negativo si descubriste una frontera nueva.

Para una receta más operativa consulta [`../howto/diagnostics.md`](../howto/diagnostics.md).
