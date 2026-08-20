# 10 — Procesos y continuaciones

Un proceso Total-Core puede continuar indefinidamente por **quanta finitos**, no mediante una ejecución indivisible infinita. Cada quantum está acotado por `quantum_steps`; si no alcanza `halt`, produce estado `SUSPENDED` y una continuación ligada al hash del programa, estado y epoch.

<!-- tevdoc-source: examples/docs/v31/tutorial/10_processes_continuations/main.tevs -->
```tevs
process Tutorial10 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.continuation End;
label End = halt;
entry Start;
```

El checkpoint siguiente incorpora la continuación anterior; reanudar con un recibo de otro programa o estado es inválido.

**Contraprueba:** un checkpoint marcado `halted` no puede reanudarse.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, `spec/TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md`.