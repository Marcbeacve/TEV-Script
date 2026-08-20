# Expresiones y operadores

Las expresiones y operadores se evalúan dentro de las unidades V2; en 3.1 son **INHERITED_COMPATIBILITY**. Total-Core no redefine precedencias ni conversión numérica. Esa decisión evita que una unidad cambie de significado sólo por ser invocada desde un proceso 3.1.

Las expresiones de control de V2 (`if ... then ... else ...`, llamadas, acceso a valores y operadores definidos por el lenguaje) pasan por tipado y lowering antes de generar Program IR V4.

En el proceso semántico superior, los cuerpos de label pertenecen a la gramática V3 heredada más la forma 3.1 `invoke_v4 UNIT result RELATION NEXT_LABEL`. `apply`, `branch_fact`, `jump` y `halt` se conservan como instrucciones semánticas; `invoke_v4` es la extensión **CURRENT**.

Autoridad: `spec/TEV_SCRIPT_V2_LANGUAGE.md`, `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.