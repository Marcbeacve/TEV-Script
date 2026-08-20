# 09 — Field, Transformation y Apply

Ésta es la base semántica central. `Field` representa hechos observados/admitidos; `Transformation` describe un cambio condicionado; `Apply` intenta materializarlo bajo sus precondiciones. No son tres metáforas: sus hashes y recibos hacen auditable la transición.

<!-- tevdoc-source: examples/docs/v31/tutorial/09_field_transformation_apply/main.tevs -->
```tevs
process Tutorial09 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.field End;
label End = halt;
entry Start;
```

`invoke_v4` crea una transformación puente derivada para añadir el resultado de la unidad como hecho, y el runtime exige que ese Apply cierre como `PASS`.

**Contraprueba:** una transformación desconocida o proof-open sin admisión exacta es rechazada por Program IR/runtime.

Autoridad: `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.