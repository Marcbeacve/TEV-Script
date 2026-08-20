# HOWTO — Efectos y capacidades

Una unidad de efectos debe declararse `profile effects` y recibir `effect_inputs` externos. No concedas una capacidad por el mero hecho de que la fuente la nombre: el proveedor del host decide qué operaciones existen y bajo qué scope.

Separa tres capas: semántica TEVScript (qué efecto se solicita); adaptador/proveedor (cómo se materializa); política de despliegue (qué se permite). Conserva los recibos de observación/transición y no conviertas excepciones del host en éxito semántico.

Para filesystem, aplica además el scope y las reglas de ruta de `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`.