# 04 — Funciones y tipos

Las firmas pertenecen a la semántica de la unidad V2. Una función declara tipos de entrada y salida; la compilación falla antes de ejecutar si el programa no respeta el contrato. Total-Core preserva esa semántica dentro de una unidad V4 `pure`.

<!-- tevdoc-source: examples/docs/v31/tutorial/04_functions_types/main.tevs -->
```tevs
process Tutorial04 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.function End;
label End = halt;
entry Start;
```

La fuente hija usa `fn add1(x:Int)->Int`. El tipo es parte del programa compilado, no una anotación decorativa.

**Contraprueba:** si el entry de una unidad `pure` no es puro, el adaptador Total-Core rechaza el perfil.

Autoridad: `spec/TEV_SCRIPT_V2_LANGUAGE.md`, `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.