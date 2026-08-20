# 05 — Modelos de datos

TEVScript dispone de valores tipados y modelos estructurados en sus perfiles heredados. El principio estable es que el valor portable tiene una codificación canónica antes de participar en hashes, recibos o estado compartido.

<!-- tevdoc-source: examples/docs/v31/tutorial/05_data_models/main.tevs -->
```tevs
process Tutorial05 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.data End;
label End = halt;
entry Start;
```

No confundas un objeto del host con un valor TEVScript. El host puede materializar estructuras propias, pero la frontera portable usa los modelos y codificaciones definidos por la versión del IR.

**Contraprueba:** datos no representables por el perfil canónico no deben incorporarse silenciosamente a la identidad semántica.

Autoridad: `spec/PORTABLE_VALUE_MODEL_V1.md`, `spec/TEV_SCRIPT_IR_V3_VALUE_MODEL.md`, `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.