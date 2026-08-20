# Total-Core 3.1

## Forma de fuente CURRENT

El header exacto es `process NAME version "3.1.0";`. Las unidades usan `unit NAME profile pure|recursive|effects;`. La extensión propia de control es `invoke_v4 UNIT result RELATION NEXT_LABEL` dentro de un `label`.

La fuente debe terminar cada declaración en `;`. Se requiere un único header. `unit_sources` debe ser un mapping con exactamente las unidades declaradas. Para `effects`, `effect_inputs` debe cubrir exactamente las unidades de ese perfil.

## Resultado

La compilación produce `TEV_SCRIPT_PROGRAM_IR_V5_TOTAL_CORE_V1`, versión de lenguaje 3.1.0, perfil `total_core`. Program IR incluye Field inicial, transformaciones, unidades V4, admisiones de prueba, instrucciones, entry PC, límite de quantum, autoridad y `program_hash`.

## Lo que no hace

3.1 no cambia V2, Program IR V4 ni el proceso semántico V3 publicado; los embebe/adapta conservando sus hashes semánticos.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.