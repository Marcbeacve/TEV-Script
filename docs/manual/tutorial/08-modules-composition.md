# 08 — Módulos y composición

La composición evita convertir un programa grande en un único script. V1/V2 proporcionan linking y módulos; Total-Core añade composición heterogénea mediante unidades V4 identificadas por `unit_id`, perfil e identidad canónica.

<!-- tevdoc-source: examples/docs/v31/tutorial/08_modules_composition/main.tevs -->
```tevs
process Tutorial08 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.module End;
label End = halt;
entry Start;
```

La tabla de unidades se ordena canónicamente; el orden accidental de un diccionario del host no cambia el programa.

**Contraprueba:** suministrar una unidad no declarada o dejar una declarada sin fuente falla con `TEVS_V31_SOURCE_UNIT_SET`.

Autoridad: `spec/TEV_SCRIPT_V1_LINK_MODEL.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.