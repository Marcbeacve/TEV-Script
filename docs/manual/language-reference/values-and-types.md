# Valores exactos y tipos

## Aplicabilidad

La mayor parte de la sintaxis de tipos de unidades `pure`/`recursive`/`effects` es **INHERITED_COMPATIBILITY V2**. Total-Core 3.1 no crea otra aritmética: integra los artefactos V4 resultantes y usa canonical JSON para Fields/receipts/identidades.

## Tipos primitivos portables V2

La superficie V2 incluye:

```text
Bool
Int
Rat
Text
Vec2
Vec3
```

`Unit` forma parte del modelo portable como retorno de determinadas fronteras, pero no se trata como un contenedor arbitrario de estado de fuente.

### `Bool`

Valores `true` y `false`. Condiciones de `if`, `while` y otros controles tipados requieren Bool.

### `Int`

Entero exacto. No está definido como `int32`, `int64` o entero nativo del host. La codificación portable usa decimal canónico.

### `Rat`

Racional exacto. La representación canónica conserva numerador/denominador en vez de aproximar a IEEE-754.

### `Text`

Texto portable. Operaciones/orden no deben depender del locale del host salvo que un contrato explícito lo introduzca.

### `Vec2` / `Vec3`

Vectores portables con componentes numéricas canónicas bajo el modelo correspondiente.

## Tipos construidos

```ebnf
type = "Bool" | "Int" | "Rat" | "Text" | "Vec2" | "Vec3"
     | identifier
     | "Option" , "<" , type , ">"
     | "Result" , "<" , type , "," , type , ">"
     | "List" , "<" , type , "," , positive-integer , ">"
     | "Array" , "<" , type , "," , positive-integer , ">"
     | "Set" , "<" , type , "," , positive-integer , ">"
     | "Map" , "<" , type , "," , type , "," , positive-integer , ">"
     | associated-type ;
```

La capacidad/longitud `N` está en `1..4096` y forma parte de la identidad del tipo.

## `Option<T>`

Familia cerrada:

```text
Some(T)
None
```

No es un alias de `null` del host. `Some(Int)` y `Some(Text)` pertenecen a tipos distintos.

## `Result<T,E>`

Familia cerrada:

```text
Ok(T)
Err(E)
```

Permite representar éxito/error como valor tipado sin convertir automáticamente cada error semántico en excepción del host.

## `List<T,N>`

Secuencia de longitud variable hasta `N`. `list.push` no puede superar la capacidad. La secuencia conserva orden.

## `Array<T,N>`

Secuencia de longitud fija `N`. Un literal o valor con longitud diferente se rechaza.

## `Set<T,N>`

Conjunto acotado. La identidad/serialización ordena valores por bytes canónicos, no por hash table del host.

## `Map<K,V,N>`

Mapa acotado. Orden canónico por bytes de clave. Duplicados canónicos se rechazan. `map.get` produce una ausencia tipada, no una semántica de excepción ambiental.

## Records genéricos

Forma:

```text
generic record Box<T> {
    value:T;
}
```

Los records son nominales. El constructor debe proporcionar el conjunto cerrado de campos y valores del tipo correcto.

Las dependencias entre records se cierran antes de ejecución. Ciclos de valor ilegales fallan.

## Associated types y protocols

V2 admite associated types dentro de protocols/impls. Una proyección tiene forma conceptual:

```text
T::Item
```

y sólo es válida si los constraints permiten resolver un único owner/proyección concreta.

La normalización ocurre antes de lowering a Program IR.

## Canonical value model

En artefactos/receipts aparecen encodings estructurados. Ejemplos conceptuales:

```text
Int 5      → {"$int":"5"}
Rat 3/2    → {"$rat":["3","2"]}
```

Records, variants y colecciones llevan su metadata/tipo canónico según el perfil.

No escribas código que dependa de `repr()` de Python o del orden de propiedades de un objeto JS para identificar un valor TEVScript.

## Igualdad y orden

La igualdad se define dentro del modelo portable cerrado. Cuando una estructura necesita orden de canonicalización, se utiliza el orden canónico especificado; no un comparator locale/host arbitrario.

## Profundidad y cierre

V2 limita el nesting de valores/tipos. Todo tipo que llegue al artefacto ejecutable debe estar cerrado y materializable; un parámetro genérico abierto no puede permanecer como tipo dinámico de runtime.

## Values en Fields Total-Core

Un `fact` Total-Core usa relación estable y argumentos strict-canonical-JSON admitidos por la base semántica. Un objeto host no se vuelve Field fact sólo por ser serializable.

La semántica de un resultado V4 se proyecta al Field mediante un payload bridge validado/canónico.

## Frontera con `float`

`float`/`double` del host no son sinónimos de `Rat`. Si una integración necesita aproximación, la conversión debe producirse de forma explícita en la frontera del host y no cambiar retrospectivamente la identidad del valor original.

## Fallos representativos

- tipo desconocido/no cerrado;
- capacity fuera de rango;
- array con longitud incorrecta;
- overflow de colección acotada;
- record con campo incorrecto;
- variant/payload incompatible;
- associated projection ambigua;
- encoding canónico malformado;
- nesting superior al límite.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/PORTABLE_VALUE_MODEL_V1.md`
- `spec/TEV_SCRIPT_IR_V3_VALUE_MODEL.md`
- `tev_script/generic_types_v2.py`
- `tev_script/ir_v4_values.py`
