# HOWTO — recetas operativas

Los HOWTO responden a una pregunta concreta: **«¿cómo hago X con la plataforma actual?»**. No sustituyen el tutorial ni la referencia del lenguaje.

Todos los comandos principales usan la CLI pública genérica `tev-script`, cuyo perfil actual es `3.1.0 / total_core`.

- [`build-and-run.md`](build-and-run.md) — comprobar, compilar y ejecutar un proyecto.
- [`multi-unit.md`](multi-unit.md) — compilar un root con varias unidades.
- [`effects-capabilities.md`](effects-capabilities.md) — preparar evidence/scenario para una unidad effects sin inventar autoridad.
- [`diagnostics.md`](diagnostics.md) — localizar y corregir un `TEVS_*`.
- [`proof-admissions.md`](proof-admissions.md) — construir y suministrar admissions externas.
- [`checkpoints-replay.md`](checkpoints-replay.md) — suspender, continuar y razonar sobre replay.

Regla transversal: source se compila en build time; runtime consume Program IR canónico. Los ejemplos no conceden filesystem/red/Unity por omisión.
