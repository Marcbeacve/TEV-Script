# Frontera fuente → IR

La ruta actual es:

`fuente 3.1 → normalización Total-Core → proceso V3 + fuentes hijas V2 → Program IR V4 por unidad → ensamblaje Program IR V5 Total-Core → validación canónica → runtime V5`.

La normalización sólo adapta la envolvente de versión/unidades/invocaciones; no autoriza reinterpretar el contenido V2/V3. Cada unidad conserva su `child_source_semantic_hash`; el programa superior deriva un `source_semantic_hash` de la estructura completa.

El IR es la frontera portable. Los hosts pueden tener objetos Python, JS o C#, pero deben convertirlos al esquema canónico y validar hashes antes de ejecutar. Campos desconocidos, tablas no canónicas o hashes divergentes fallan cerrados.

Autoridad: `tev_script/source_total_core_v31.py`, `tev_script/program_ir_v5_total.py`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.