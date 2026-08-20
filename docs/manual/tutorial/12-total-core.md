# 12 — Total-Core 3.1

Total-Core es el perfil actual del lenguaje 3.1.0. Combina el proceso semántico heredado de V3 con unidades V4 y la instrucción `invoke_v4`, sin reinterpretar los artefactos publicados de V2/V3/V4.

<!-- tevdoc-source: examples/docs/v31/tutorial/12_total_core/main.tevs -->
```tevs
process Tutorial12 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.total End;
label End = halt;
entry Start;
```

La compilación produce `TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1`. El `source_semantic_hash` liga el proceso V3, las semánticas hijas y el mapa de invocaciones.

**Contraprueba:** el frontend 3.1 rechaza otro número de versión con `TEVS_V31_SOURCE_VERSION`.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.