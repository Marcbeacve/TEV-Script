# 01 — Valores y exactitud

TEVScript separa **valor semántico** de representación del host. Para el código V2 embebido, `Int` es exacto: `4`, `1` y `5` no dependen de coma flotante. En Total-Core, el proceso 3.1 no reinterpreta la semántica de la unidad hija; la compila a Program IR V4 y liga su identidad por hash.

## Ejemplo ejecutable

<!-- tevdoc-source: examples/docs/v31/tutorial/01_values_exactness/main.tevs -->
```tevs
process Tutorial01 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.value End;
label End = halt;
entry Start;
```

La unidad `Calc` devuelve un entero exacto. `invoke_v4` no copia una aproximación del resultado: inserta en el Field una evidencia canónica del recibo V4.

**Contraprueba:** cambiar `version "3.1.0"` por otra versión debe producir `TEVS_V31_SOURCE_VERSION`.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, `spec/TEV_SCRIPT_V2_LANGUAGE.md`.