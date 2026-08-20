# 03 — Control y cotas

TEVScript admite computación recursiva cuando existe un contrato de descenso y una cota explícita. La terminación operacional no se deja a una suposición del host: la unidad `recursive` conserva su presupuesto al convertirse a Program IR V4 Recursive.

<!-- tevdoc-source: examples/docs/v31/tutorial/03_control_bounds/main.tevs -->
```tevs
process Tutorial03 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Rec result tev.tutorial.recursive End;
label End = halt;
entry Start;
```

<!-- tevdoc-source: examples/docs/v31/tutorial/03_control_bounds/rec.tevs -->
```tevs
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

`decreases n` aporta la medida de progreso y `max_depth 8` un límite finito. Además, el proceso dispone de `quantum_steps`, independiente de la cota interna de la unidad.

**Contraprueba:** una unidad declarada `recursive` cuyo entry sea puro falla con `TEVS_V31_SOURCE_UNIT_PROFILE`.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.