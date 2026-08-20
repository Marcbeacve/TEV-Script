# 15 — Aplicación completa

La aplicación final compone dos unidades con perfiles diferentes. Total-Core conserva cada semántica hija, ejecuta primero `Calc`, proyecta su recibo al Field y después ejecuta `Rec`. El proceso padre coordina; no absorbe las implementaciones hijas.

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/main.tevs -->
```tevs
process Tutorial15 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 16;
unit Calc profile pure;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Calc result tev.app.calc AfterCalc;
label AfterCalc = invoke_v4 Rec result tev.app.rec End;
label End = halt;
entry Start;
```

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/calc.tevs -->
```tevs
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/rec.tevs -->
```tevs
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

Lo esencial es la frontera: V2 resuelve cada unidad; V4 fija su IR; V5 Total-Core coordina mediante hashes, Field y recibos.

**Contraprueba:** si falta `Rec` en `unit_sources`, la compilación falla cerrada con `TEVS_V31_SOURCE_UNIT_SET`.

Autoridad: `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.