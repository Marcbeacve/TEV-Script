# 08 — Módulos, unidades y composición

Un programa grande no debería convertirse en un único archivo ni en una única semántica monolítica. TEVScript usa varias formas de composición según la generación del lenguaje: linking/módulos en V1/V2 y **unidades V4 content-addressed** dentro del proceso Total-Core V5.

Este capítulo demuestra la segunda forma con dos unidades de perfiles diferentes.

## Ejemplo ejecutable: pure + recursive

<!-- tevdoc-source: examples/docs/v31/tutorial/08_modules_composition/main.tevs -->
```tevs
process Tutorial08 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
unit Rec profile recursive;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.module.pure Second;
label Second = invoke_v4 Rec result tev.tutorial.module.recursive End;
label End = halt;
entry Start;
```

La unidad `Calc` es pura:

<!-- tevdoc-source: examples/docs/v31/tutorial/08_modules_composition/calc.tevs -->
```tevs
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

La unidad `Rec` usa recursión contratada:

<!-- tevdoc-source: examples/docs/v31/tutorial/08_modules_composition/rec.tevs -->
```tevs
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

El caso documental compila ambas unidades y ejecuta el proceso completo hasta `HALTED`.

## Qué es una unidad V5 Total-Core

El root V5 no copia la lógica interna de la unidad. Guarda un objeto que liga:

```text
unit_id
profile = pure | recursive | effects
program_ir_v4
program_ir_hash
unit_hash
```

El `program_ir_v4` se valida con **su propio validador V4**. V5 no tiene una segunda implementación de la aritmética pura o de la recursión.

## Perfil exacto

La correspondencia es cerrada:

```text
pure      → TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1
recursive → TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1
effects   → TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1
```

Declarar `unit Rec profile pure` mientras la fuente produce un entry recursivo falla. El nombre del perfil no es una etiqueta informal.

## `unit_id` y `unit_hash`

`unit_id` es el nombre estable usado por la fuente del proceso. `unit_hash` liga ese ID, el perfil y el `program_ir_hash` hijo. Dos unidades no pueden compartir el mismo ID dentro de un programa.

El hash permite referenciar el artefacto exacto desde `invoke_v4` sin confiar en una ruta de archivo de build.

## Orden de tabla frente a orden de ejecución

Hay dos órdenes distintos:

1. la **tabla de unidades** se canonicaliza por `(unit_id, unit_hash)`;
2. la **tabla de instrucciones** conserva el orden de control del programa.

Por eso cambiar el orden de un diccionario Python que aporta `{"Calc": ..., "Rec": ...}` no debe cambiar la identidad del programa; cambiar `Start → Second → End` sí cambia el control semántico.

## `invoke_v4`

En el ejemplo la primera invocación añade un fact puente con relación:

```text
tev.tutorial.module.pure
```

y la segunda usa:

```text
tev.tutorial.module.recursive
```

Cada fact liga como mínimo identidad de unidad, hash del IR hijo y hash del receipt. Para pure/recursive incluye además resultado tipado/canónico y coste de evaluación.

## Composición no es memoria compartida

`Calc` y `Rec` no comparten globals. Cada unidad es un artefacto cerrado. La comunicación observable hacia el padre se produce por el bridge fact y, para otros perfiles, mediante contratos explícitos.

Esto reduce acoplamiento y evita que un módulo pueda modificar accidentalmente el estado interno de otro.

## Módulos V1/V2

Las generaciones anteriores también poseen linking/módulos. Esas superficies siguen siendo compatibilidad y conservan su propia identidad. Total-Core no convierte automáticamente un import V2 en un `unit` V5 ni viceversa.

Piensa en dos niveles:

```text
composición interna de una unidad V2
        ↓ compila a
Program IR V4 cerrado
        ↓ se incorpora como
unidad hija de Total-Core V5
```

## Conjunto exacto de fuentes

Al compilar Total-Core, el conjunto de `unit_sources` debe coincidir exactamente con lo declarado por `unit`:

- una unidad declarada sin fuente: error;
- una fuente adicional no declarada: error;
- mismo `unit_id` dos veces: error.

Esto evita que el filesystem/build system introduzca código accidental fuera del modelo semántico.

## Cuándo separar una unidad

Una unidad merece frontera propia cuando aporta una computación cerrada que puede validarse con su perfil: por ejemplo un cálculo puro, una función recursiva bien fundada o una computación effects con evidencia externa explícita.

No conviene usar unidades como sustituto de cada función pequeña: la granularidad útil es la de una autoridad computacional cerrada y reutilizable.

## Autoridad técnica

- `spec/TEV_SCRIPT_V1_LINK_MODEL.md` para linking histórico.
- `spec/TEV_SCRIPT_V2_LANGUAGE.md` para módulos/fuente V2.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, secciones V4 child units y ordering.
- `tev_script/source_total_core_v31.py`.
