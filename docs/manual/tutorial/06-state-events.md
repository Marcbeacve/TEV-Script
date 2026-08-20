# 06 — Estado y eventos

En TEVScript histórico/V2 existen declaraciones de estado y eventos. En Total-Core, el estado semántico del proceso superior es un `Field`; los cambios admisibles se expresan mediante `Transformation` y se ejecutan con `Apply`. El host no puede mutar ese Field por fuera de la transición validada.

<!-- tevdoc-source: examples/docs/v31/tutorial/06_state_events/main.tevs -->
```tevs
process Tutorial06 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.state End;
label End = halt;
entry Start;
```

El recibo de la unidad se proyecta al Field como un hecho. Eso es distinto de permitir que la unidad modifique arbitrariamente el proceso padre.

**Contraprueba:** una transición cuyo `required_before_hash` no coincide con el Field observado no puede cerrarse como Apply válido.

Autoridad: `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`, `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.