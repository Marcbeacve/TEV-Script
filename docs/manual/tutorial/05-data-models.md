# 05 — Modelos de datos, records y colecciones

TEVScript necesita representar datos estructurados sin depender del layout de objetos de Python, JavaScript o CLR. Para eso usa tipos portables, nominales y/o construidos cuya identidad puede cerrarse antes de runtime.

Este capítulo introduce records genéricos y las colecciones acotadas. El objetivo no es memorizar sintaxis, sino entender qué información forma parte del tipo y de la identidad canónica.

## Ejemplo ejecutable: `Box<T>`

<!-- tevdoc-source: examples/docs/v31/tutorial/05_data_models/main.tevs -->
```tevs
process Tutorial05 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.data End;
label End = halt;
entry Start;
```

La unidad hija usa exactamente el patrón de record genérico ejercitado end-to-end por la suite V2:

<!-- tevdoc-source: examples/docs/v31/tutorial/05_data_models/calc.tevs -->
```tevs
script DataModels version "2.0.0";
generic record Box<T> { value: T; }
generic fn box<T>(x:T)->Box<T>=Box(value=x);
entry main:Box<Int>=box<Int>(7);
```

`Box<Int>` es un tipo nominal materializado a partir del template `Box<T>` y del argumento de tipo `Int`.

## Records nominales

La declaración:

```text
generic record Box<T> { value:T; }
```

crea una familia de tipos. No equivale a «cualquier diccionario con una clave `value`». El constructor `Box(value=x)` debe respetar el conjunto y los tipos de campos declarados.

Los campos se canonicalizan según el contrato; el orden superficial de declaraciones independientes o el formato del archivo no se usa como sustituto de semántica.

## Records anidados

Los records pueden depender de otros records genéricos cuando el grafo de tipos es cerrable y no introduce ciclos ilegales. La suite incluye, por ejemplo, un `Wrapper<T>` que contiene `Box<T>` y demuestra que reordenar declaraciones independientes no altera la identidad semántica.

Un ciclo de valores como `A<T> -> B<T> -> A<T>` que no pueda cerrarse bajo el modelo permitido se rechaza antes de mutar el registro de tipos.

## `Option<T>` y `Result<T,E>`

Estas familias representan alternativas cerradas y tipadas:

```text
Option<T>   = Some(T) | None
Result<T,E> = Ok(T)   | Err(E)
```

No son `null`/excepciones arbitrarias del host. El tipo del payload forma parte de la variante y `match` debe respetar la exhaustividad correspondiente.

## Colecciones acotadas

Las colecciones portables incorporan su capacidad máxima en el tipo:

```text
List<Int,4>
Array<Text,8>
Set<Int,16>
Map<Text,Int,32>
```

`List<Int,4>` no puede crecer a cinco elementos. Un `list.push` que excedería la capacidad falla; el runtime no redimensiona silenciosamente el contenedor.

## Orden y canonicalización

Cada familia tiene una política de orden relevante:

- `List` y `Array`: preservan secuencia;
- `Set`: orden canónico por bytes del valor;
- `Map`: orden canónico por bytes de la clave.

Por ello un `Map` no hereda el orden accidental de inserción de un diccionario del host como parte de su identidad semántica.

## Acceso seguro

Operaciones como `array.get`, `list.get`, `map.get`, `list.push` y `map.put` son primitivas tipadas dentro del perfil correspondiente. Sus tipos de entrada/salida se conocen antes de ejecutar.

Un ejemplo probado por la suite es:

```text
generic fn lookup<T>(m:Map<Text,T,4>, key:Text)->Option<T>=map.get(m,key);
```

La ausencia de una clave produce un `Option<T>`, no una excepción ambiental obligatoria del host.

## `match`

`Option`, `Result` y enums cerrados pueden eliminarse mediante `match`. El contrato exige brazos compatibles y exhaustivos; duplicar una variante o omitir una requerida es un error estático/validado.

## Límites de nesting

El modelo portable fija límites de anidamiento. Esto impide que una estructura host arbitrariamente profunda entre al IR simplemente porque puede serializarse como JSON.

## Field facts no son objetos libres

Total-Core usa `Field` para estado semántico. Los argumentos de un fact deben ser datos canónicos admitidos. Meter un `dict` Python en un Field sin pasar por el modelo/normalización adecuada no lo convierte en un valor TEVScript.

## Identidad y hashes

Tipos, constructors, capacidades de colección y payloads canónicos contribuyen a las identidades correspondientes. Los hashes sirven para comprobar identidad/integridad del contenido bajo el contrato; no transforman el dato en una prueba empírica.

## Errores comunes

- campo ausente o adicional en un record cerrado;
- valor de campo con tipo incorrecto;
- capacidad de colección excedida;
- longitud de `Array<T,N>` distinta de `N`;
- clave/elemento duplicado cuando el contrato lo prohíbe;
- tipo genérico no cerrado;
- ciclo de records no admitido;
- `match` no exhaustivo o con brazos duplicados.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`.
- `spec/PORTABLE_VALUE_MODEL_V1.md`.
- `tev_script/generic_types_v2.py` y `tev_script/source_program_v2.py`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md` para la frontera V5/V4.
