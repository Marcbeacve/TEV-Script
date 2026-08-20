# Léxico, comentarios e identificadores

## Clasificación

`# comentario` es **CURRENT** en el wrapper Total-Core: la normalización elimina líneas cuyo primer carácter no blanco es `#`. Los comentarios y reglas léxicas de las unidades V2 son **INHERITED_COMPATIBILITY** y se rigen por su especificación.

Los identificadores estables de proceso, unidad, label y relación aceptados por Total-Core siguen el patrón `^[A-Za-z_][A-Za-z0-9_.:/-]*$`. No deben usarse nombres cuya validez dependa del locale del host.

Las declaraciones Total-Core terminan en `;`. Un texto residual sin punto y coma genera `TEVS_V31_SOURCE_SEMICOLON`. Cadenas o arrays sin cerrar generan `TEVS_V31_SOURCE_UNCLOSED`; `]` sin apertura genera `TEVS_V31_SOURCE_BRACKETS`.

El frontend requiere texto. Los bytes de archivo se decodifican como UTF-8 en la CLI V31 y una fuente inválida produce `TEVS_V31_SOURCE_UTF8`.

Autoridad: `tev_script/source_total_core_v31.py`, `tev_script/cli_v31.py`, `spec/TEV_SCRIPT_V1_LEXICAL_PROFILE.md`.