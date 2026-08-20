# Módulos y composición

El linking de módulos V1/V2 es **INHERITED_COMPATIBILITY**. La composición Total-Core es **CURRENT** y opera sobre unidades V4: cada unidad tiene `unit_id`, `profile`, Program IR V4, `program_ir_hash` y `unit_hash`.

La fuente del proceso declara el conjunto exacto de unidades. `compile_total_core_v31(..., unit_sources=...)` exige igualdad de conjuntos entre nombres declarados y suministrados. No existen imports implícitos desde el filesystem del host.

Las tablas de unidades, transformaciones y admisiones se ordenan canónicamente para que el hash no dependa del orden accidental de construcción.

Autoridad: `spec/TEV_SCRIPT_V1_LINK_MODEL.md`, `tev_script/source_total_core_v31.py`, `tev_script/program_ir_v5_total.py`.