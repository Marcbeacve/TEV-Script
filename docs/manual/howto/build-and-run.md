# HOWTO — Comprobar, compilar y ejecutar

1. Escribe el proceso 3.1 y las fuentes de sus unidades.
2. Usa `check` para validar sin producir artefacto.
3. Usa `compile` con `--output` para materializar Program IR canónico.
4. Usa `run` con un número finito de `--epochs`; si necesitas persistencia, añade `--checkpoint-output`.
5. Para reanudar, valida primero que el checkpoint pertenece al mismo `program_hash`.

No edites a mano el `program_hash`: cualquier modificación del contenido exige reconstruir y revalidar el artefacto.

Consulta: `cli-reference/check.md`, `compile.md`, `run.md` y `tutorial/15-complete-application.md`.