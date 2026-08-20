# 02 — Nombres, bindings y expresiones

Los identificadores enlazan entidades semánticas; no son direcciones de memoria. En un proceso Total-Core, `unit Calc`, `label Start` y la relación `tev.tutorial.binding` tienen identidades estables. En la unidad V2, parámetros y bindings se resuelven antes del lowering.

<!-- tevdoc-source: examples/docs/v31/tutorial/02_names_bindings/main.tevs -->
```tevs
process Tutorial02 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.binding End;
label End = halt;
entry Start;
```

La expresión del hijo se tipa y evalúa según V2; el proceso sólo conoce la unidad por perfil, hash y recibo.

**Contraprueba:** declarar dos unidades con el mismo identificador se rechaza con `TEVS_V31_SOURCE_UNIT_DUPLICATE`.

Autoridad: `spec/TEV_SCRIPT_V2_LANGUAGE.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.