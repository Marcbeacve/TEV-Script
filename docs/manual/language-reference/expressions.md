# Expresiones

## Aplicabilidad

Las expresiones de esta página pertenecen principalmente a la fuente **V2 compatible** que se compila dentro de unidades V4. El root Total-Core no es un lenguaje de expresiones generales: su control se expresa mediante facts/transforms/labels/instrucciones.

## Forma general V2

La especificación admite familias como:

```ebnf
expression = literal | identifier | field-expression | call-expression
           | constructor-expression | collection-expression
           | unary-expression | binary-expression
           | "if" , expression , "then" , expression , "else" , expression
           | match-expression | for-expression | while-expression
           | task-expression | step-limit-expression | select-expression ;
```

Cada expresión tiene tipo estático y un límite de evaluación derivable por el compilador.

## Literales

Incluyen `Bool`, números, strings y literales contextuales de colecciones/constructores conforme al tipo esperado.

Un literal de colección no significa «lista Python»: el contexto de tipo determina `List`, `Array`, etc. y se aplican capacidad/longitud.

## Referencias a nombres

Un identifier debe resolver de forma única en el scope léxico. No existe lookup dinámico al host.

## Llamadas

Forma típica:

```text
add1(4)
identity<Int>(7)
```

La aridad y tipos se comprueban antes de runtime. Las llamadas genéricas internas usan type arguments explícitos cuando el contrato lo exige.

Los argumentos se evalúan determinísticamente bajo el perfil puro.

## Operadores numéricos

`Int`/`Rat` soportan la aritmética exacta admitida por el contrato. Entre los operadores ejercitados por la implementación están suma, resta, multiplicación y división, con ensanchamiento controlado Int→Rat cuando corresponde.

La división por cero falla cerrada; no produce `NaN` o `Infinity` portable.

## Comparación, igualdad y lógica

Comparaciones y igualdad son tipadas. La lógica booleana preserva el short-circuit especificado. No se usa coerción truthy/falsy del host.

## `if`

Forma:

```text
if condición then expresiónA else expresiónB
```

- condición: `Bool`;
- ambas ramas: mismo tipo estático/resultante admitido;
- sólo se evalúa la rama seleccionada.

## `match`

Forma conceptual:

```text
match value {
    Some(x) => ...;
    None    => ...;
}
```

Para `Option`, `Result` y enums cerrados, el match debe ser exhaustivo y no contener arms duplicados/inaccesibles. Las bindings de pattern son inmutables y locales al arm.

La rama no seleccionada no se evalúa.

## Construcción/acceso de records

Los constructors usan nombres/campos tipados, por ejemplo:

```text
Box(value=x)
```

El acceso a campo se valida contra el record nominal. El orden de campos superficial puede canonicalizarse; campos extra/faltantes no se toleran.

## Operaciones de colección

Familias probadas incluyen:

```text
list.push
list.get
array.get
array.set
set.add
set.contains
map.put
map.get
```

La operación respeta la capacidad/tipo del contenedor y no muta una estructura host compartida; produce valores bajo la semántica persistente correspondiente.

## `for ... fold`

Itera una colección de cardinalidad acotada y actualiza un accumulator inmutable:

```text
for x in xs fold acc:Int=0 do ...
```

Para `Map`, la forma puede ligar key/value. El máximo de iteraciones deriva del tipo de colección.

## `while ... max_iterations`

No existe un while ilimitado portable. La forma incluye un máximo explícito:

```text
while acc:Int=initial when condición max_iterations N do body
```

`N` está en `1..4096`. El resultado es el accumulator cuando la condición se vuelve falsa o se agota la cota.

## Tareas puras

V2 modela tareas como DAG de computación pura, no threads con memoria compartida. La superficie incluye `task scope`, `spawn`, `await`, `await all` y selección acotada.

Worker count/scheduling no puede cambiar el valor canónico.

## `within_steps`

Permite declarar presupuesto local explícito:

```text
within_steps N do expression
```

`N` está en `1..1_000_000`. Cruzar el presupuesto falla antes de ejecutar el paso adicional.

## `select first_within`

Evalúa candidatos bajo bounds declarados y selecciona el primero, según política determinista/orden léxico admitido, que completa dentro de su cota. Los perdedores especulativos no pueden filtrar effects.

## Pureza

Una expresión pure no obtiene filesystem/network/clock por escribir el nombre de una API. Llamadas como `open(...)`, `eval(...)` o `network.get(...)` que no pertenecen a la superficie admitida fallan en compilación.

## Límites

- nesting de expresión V2: máximo 128;
- pure inlining depth: máximo 64;
- colecciones/tareas: límites del tipo/perfil;
- toda evaluación pura obtiene un upper bound conservador de steps.

## Fallos representativos

- nombre no resuelto;
- aridad incorrecta;
- tipos de operandos incompatibles;
- retorno/branch con tipo incorrecto;
- división por cero;
- match no exhaustivo;
- capacidad agotada;
- bound de loop/steps inválido;
- intento de host call no declarada.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `tev_script/source_program_v2.py`
- `tev_script/ir_v4_pure.py`
