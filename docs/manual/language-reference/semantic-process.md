# Proceso semántico V3

El proceso semántico es **INHERITED_COMPATIBILITY** desde V3 y constituye la columna de control que Total-Core reutiliza. Sus conceptos centrales son `process`, `authority`, `quantum_steps`, `field`, `label` y `entry`.

Las instrucciones heredadas son `apply`, `branch_fact`, `jump` y `halt`. El frontend 3.1 traduce temporalmente sus declaraciones a la versión V3 admitida, compila con `parse_semantic_process_v3`/`compile_semantic_process_v3` y vuelve a ensamblar un programa V5 Total-Core. No modifica la semántica V3 publicada.

`source_semantic_hash` en 3.1 liga el hash semántico del proceso V3, las semánticas de las unidades hijas y la tabla de `invoke_v4`.

Autoridad: `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`, `tev_script/source_total_core_v31.py`.