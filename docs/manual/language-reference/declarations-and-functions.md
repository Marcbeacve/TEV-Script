# Declaraciones y funciones

En una unidad V2, `script`, `fn`, funciones recursivas, declaraciones de tipo/estado y `entry` son **INHERITED_COMPATIBILITY**. Sus firmas, parámetros, retornos y restricciones se validan antes del lowering.

En un proceso 3.1 son **CURRENT**: `process NAME version "3.1.0";`, `authority HASH;`, `quantum_steps N;`, `unit NAME profile PROFILE;`, `field NAME = ...;`, `label NAME = ...;` y `entry NAME;`.

`unit` no define una función; declara una frontera hacia un artefacto hijo. El perfil debe ser exactamente `pure`, `recursive` o `effects` y debe coincidir con la naturaleza del entry de la fuente hija.

Duplicar el header, una unidad o un label de invocación se rechaza. La autoridad es un hash de 64 hex minúsculas validado por la capa de proceso heredada.

Autoridad: `tev_script/source_total_core_v31.py`, `spec/TEV_SCRIPT_V2_LANGUAGE.md`.