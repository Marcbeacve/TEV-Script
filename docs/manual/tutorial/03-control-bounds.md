# 03 — Control, terminación local y límites

TEVScript no necesita prohibir toda computación prolongada para conservar control operacional. La estrategia es exigir que **cada mecanismo que puede crecer tenga un contrato finito verificable**. En V2 eso incluye iteración, recursión y tareas; en Total-Core 3.1 la ejecución global se divide además en quanta finitos.

## Recursión ejecutable: factorial

El caso de este capítulo es el mismo patrón que usa la suite Total-Core para demostrar que una unidad `recursive` V4 se compila y ejecuta con su autoridad propia.

<!-- tevdoc-source: examples/docs/v31/tutorial/03_control_bounds/main.tevs -->
```tevs
process Tutorial03 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Rec result tev.tutorial.recursion End;
label End = halt;
entry Start;
```

<!-- tevdoc-source: examples/docs/v31/tutorial/03_control_bounds/rec.tevs -->
```tevs
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

La función calcula `factorial(5)`, pero la característica interesante no es el 120: es que la recursión lleva un **testigo de progreso** y un **límite de profundidad**.

## `decreases n`

`decreases n` declara la medida de descenso. El parámetro elegido debe instanciarse como `Int`, y cada `self(...)` recursivo debe disminuir estrictamente esa medida.

En el ejemplo:

```text
n → n - 1
```

por lo que la cadena esperada es finita:

```text
5 → 4 → 3 → 2 → 1 → 0
```

Una llamada `self(n)` no demuestra descenso y se rechaza.

## `max_depth 8`

Incluso con una medida válida, el contrato conserva un máximo explícito. Si una ejecución necesitara cruzar el `max_depth`, falla cerrada sin fabricar un resultado parcial.

El límite forma parte de la identidad del callable recursivo. Cambiar `max_depth 4` por `max_depth 8` no es un detalle de rendimiento invisible: cambia el contrato admitido.

## `max_steps`

V2 admite además un presupuesto de pasos para funciones recursivas. Cuando se declara, la ejecución no puede cruzarlo silenciosamente. El objetivo es que el coste operacional relevante permanezca acotado por artefactos verificables.

## Forma de la recursión

La recursión contratada no es un `goto` arbitrario:

- sólo aparece en `recursive fn`;
- usa `self(...)` directo;
- la medida debe disminuir;
- `self` en condiciones o dentro de loops está restringido/prohibido por el contrato vigente;
- múltiples self-calls estáticos que rompan el perfil admitido fallan;
- la recursión mutua no se introduce implícitamente.

## Iteración acotada

V2 también dispone de formas de iteración cuyo máximo se deriva del tipo o se declara explícitamente. Dos ideas importantes son:

```text
for ... fold ...
while ... max_iterations N ...
```

Un `List<T,4>` ya contiene un máximo de cardinalidad en su tipo. Un `while` exige `max_iterations`. El lenguaje no transforma una ausencia de prueba de terminación en un loop infinito ambientemente permitido.

## Quanta Total-Core

Total-Core añade otro nivel de control. El proceso raíz declara:

```text
quantum_steps 8
```

Un quantum ejecuta como máximo ese número de instrucciones V5. Si el proceso global debe continuar, lo hace mediante checkpoint/continuation explícitos.

Así se separan dos nociones:

```text
terminación de una unidad computacional
≠
vida global de un proceso
```

Una aplicación puede ser abierta en el tiempo sin que una operación individual tenga presupuesto infinito.

## `jump`, `branch_fact` y `halt`

El control V5 Total-Core tiene un conjunto cerrado de instrucciones:

```text
apply
branch_fact
jump
halt
invoke_v4
```

Todos los destinos de program counter deben quedar dentro de la tabla de instrucciones. `halt` cierra el quantum/programa en el estado correspondiente; no es una excepción del host.

## Por qué esto importa

Los límites forman parte de la seguridad semántica y operacional:

- evitan que un backend convierta una operación acotada en una búsqueda sin fin;
- permiten presupuestar recursos;
- hacen reproducibles los fallos por agotamiento;
- permiten continuar procesos abiertos con receipts/checkpoints en vez de ocultar un loop eterno.

## Errores/negativos a conocer

- medida recursiva no decreciente;
- medida inicial inválida;
- profundidad agotada;
- self-call en posición no admitida;
- `while` sin cota válida;
- target de PC fuera de la tabla;
- `entry_pc` fuera del programa;
- `quantum_step_limit` fuera de `1..1_000_000`.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`, sección de recursión/iteración.
- `tev_script/recursive_functions_v2.py`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, instrucciones y límites V5.
- `tev_script/runtime_v5_total.py`, ejecución por quanta.
