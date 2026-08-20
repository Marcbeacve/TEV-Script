# 14 — Checkpoints y replay

Un checkpoint Total-Core liga `program_hash`, Field, PC, índice del próximo epoch, continuación previa y estado halted. Su hash permite reanudar de forma reproducible y detectar sustituciones de programa o estado.

<!-- tevdoc-source: examples/docs/v31/tutorial/14_checkpoints_replay/main.tevs -->
```tevs
process Tutorial14 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.checkpoint End;
label End = halt;
entry Start;
```

`initial_total_core_checkpoint()` crea epoch 0 sin continuación previa. Cada quantum genera una continuación y un checkpoint sucesor; replay sólo es válido si todas las identidades coinciden.

**Contraprueba:** un `program_hash` distinto produce `TEVS_V31_RUNTIME_CHECKPOINT_PROGRAM`.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, `tev_script/runtime_v5_total.py`.