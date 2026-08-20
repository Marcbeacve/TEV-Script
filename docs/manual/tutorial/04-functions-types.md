# 04 — Funciones, tipos y genéricos

Una firma TEVScript es un contrato estático, no documentación opcional. Antes de ejecutar, el compilador debe conocer el tipo de cada parámetro, del retorno y de las operaciones que aparecen en el cuerpo.

V2 ofrece funciones puras ordinarias, funciones genéricas y funciones recursivas contratadas. Total-Core 3.1 puede incorporar una unidad V2 compilada a V4 sin reinterpretar esas reglas.

## Ejemplo ejecutable: una función genérica

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

La unidad hija usa una forma probada por la suite de fuente V2:

<!-- tevdoc-source: examples/docs/v31/tutorial/04_functions_types/calc.tevs -->
```tevs
script TypedChoice version "2.0.0";
generic fn choose<T>(flag:Bool,a:T,b:T)->T=if flag then a else b;
entry main:Int=choose<Int>(true,7,9);
```

`choose<T>` no tiene un tipo dinámico. Declara una familia finita de especializaciones posibles. El `entry` selecciona explícitamente `T = Int`.

## Función ordinaria

La forma general es:

```text
fn nombre(p1:Tipo1,p2:Tipo2)->Retorno=expresión;
```

Los parámetros son bindings inmutables y la expresión debe tipar exactamente como `Retorno` bajo las reglas de ensanchamiento admitidas.

## Función genérica

La forma genérica introduce parámetros de tipo:

```text
generic fn identity<T>(x:T)->T=x;
```

Una llamada proporciona argumentos de tipo explícitos cuando el contrato lo exige:

```text
identity<Int>(7)
```

TEVScript no delega esta elección al tipo dinámico de un objeto Python/JS. El compilador monomorfiza la especialización concreta y liga su identidad al template y a los tipos elegidos.

## Tipos base

El modelo V2 portable incluye, entre otros:

```text
Bool
Int
Rat
Text
Vec2
Vec3
```

`Unit` existe como tipo de retorno de ciertas fronteras/capabilities, pero no es un contenedor libre de estado de fuente.

## Tipos construidos

Las familias construidas incluyen:

```text
Option<T>
Result<T,E>
List<T,N>
Array<T,N>
Set<T,N>
Map<K,V,N>
```

La capacidad `N` forma parte de la identidad del tipo. `List<Int,4>` y `List<Int,8>` no son el mismo tipo.

## Tipos nominales

Los records genéricos son nominales. Que dos records tengan campos de igual forma no los convierte automáticamente en el mismo tipo. La identidad incorpora su declaración/owner canónico.

## `if` tipado

En `choose<T>` ambas ramas retornan `T`. El compilador no espera a runtime para descubrir si una rama produce `Int` y otra `Text`: esa inconsistencia es estática.

El predicado debe ser `Bool`.

## Inferencia deliberadamente limitada

El lenguaje favorece tipos explícitos donde la identidad debe ser inequívoca. Por ejemplo, las llamadas genéricas internas requieren argumentos de tipo explícitos en el perfil probado. Esto evita que pequeñas diferencias de algoritmo de inferencia entre compiladores alteren el programa semántico.

## Tipo de `entry`

El entry puro declara también su tipo:

```text
entry main:Int=choose<Int>(true,7,9);
```

Si se escribiera `entry main:Text=...` con una especialización que retorna `Int`, la compilación falla. No se realiza una conversión implícita arbitraria para «hacerlo funcionar».

## Pureza como parte del perfil

Una unidad declarada por Total-Core como:

```text
unit Calc profile pure;
```

debe contener un artefacto V4 cuyo schema sea exactamente `TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1`. Si el entry hijo es recursivo o effects, el adaptador rechaza la discrepancia de perfil.

## Identidad de especialización

Cambiar `choose<Int>` por otra especialización puede cambiar tipos materializados, callable IDs, IR y hashes. El tipo no es metadata decorativa: participa en el significado canónico.

## Errores comunes

- aridad de llamada incorrecta;
- tipo de argumento incompatible;
- retorno que no coincide con la firma;
- entry declarado con un tipo distinto del resultado;
- tipo genérico no cerrado;
- especialización no admitida por sus constraints;
- unidad Total-Core cuyo perfil no coincide con el schema V4 hijo.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`.
- `tev_script/source_program_v2.py`.
- `tev_script/generic_functions_v2.py`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
