# Referencia del lenguaje TEVScript

Esta sección describe la superficie de fuente que puede encontrar un programador en el sistema actual. La clasificación es deliberada:

- **CURRENT**: fuente propia de TEVScript 3.1.0 `total_core`.
- **INHERITED_COMPATIBILITY**: fuente V2/V3 que 3.1 reutiliza sin reinterpretarla.
- **INTERNAL**: estructura de implementación/IR, no sintaxis que deba escribir el usuario.
- **REJECTED**: forma no admitida por el frontend correspondiente.

TEVScript 3.1 es aditivo: el proceso superior usa `process ... version "3.1.0"`, declara unidades V4 y puede usar `invoke_v4`; las unidades `pure`, `recursive` y `effects` continúan compilándose bajo la autoridad de V2 y Program IR V4.

Índice: léxico; valores y tipos; expresiones; declaraciones y funciones; control y cotas; estado/eventos/efectos; módulos; proceso semántico; Field/Transformation/Apply; Total-Core; admisiones de prueba; frontera source→IR.

Autoridad primaria: `spec/TEV_SCRIPT_V2_LANGUAGE.md`, `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.