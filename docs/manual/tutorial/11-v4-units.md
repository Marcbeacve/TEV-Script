# 11 — Unidades Program IR V4

Total-Core admite tres perfiles de unidad: `pure`, `recursive` y `effects`. Cada uno debe contener exactamente el esquema Program IR V4 correspondiente. El perfil declarado no puede mentir sobre el IR embebido.

<!-- tevdoc-source: examples/docs/v31/tutorial/11_v4_units/main.tevs -->
```tevs
process Tutorial11 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.v4 End;
label End = halt;
entry Start;
```

La unidad queda ligada por `program_ir_hash` y `unit_hash`. El proceso llama al hash de unidad materializado, no a código arbitrario del host.

**Contraprueba:** un esquema V4 que no corresponda al perfil genera `TEVS_V31_TOTAL_UNIT_SCHEMA`.

Autoridad: `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.