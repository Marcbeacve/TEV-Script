# 02 — Nombres, bindings y expresiones

TEVScript favorece nombres resueltos estáticamente y bindings inmutables. La pregunta que intenta responder el compilador antes de ejecutar es: **¿qué entidad significa exactamente este nombre y qué tipo tiene en este punto?**

En una unidad pura V2 no existe autoridad implícita para buscar variables globales del host, leer el entorno o resolver nombres dinámicamente. Si un nombre no pertenece al programa admitido, el compilador falla.

## Ejemplo ejecutable

<!-- tevdoc-source: examples/docs/v31/tutorial/02_names_bindings/main.tevs -->
```tevs
process Tutorial02 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.binding End;
label End = halt;
entry Start;
```

La unidad hija ya no es el `add1` genérico usado por otros capítulos: aquí los dos parámetros son bindings reales del ejemplo.

<!-- tevdoc-source: examples/docs/v31/tutorial/02_names_bindings/calc.tevs -->
```tevs
script Bindings version "2.0.0";
fn sum(a:Int,b:Int)->Int=a+b;
entry main:Int=sum(4,5);
```

`a` y `b` existen sólo dentro del cuerpo de `sum`. El `entry` proporciona los argumentos `4` y `5`, y el resultado tiene tipo `Int`.

## Resolución léxica

Los parámetros de una función forman un scope léxico. La expresión:

```text
a + b
```

no pregunta al host qué significan `a` y `b`; ambos nombres ya están ligados por la firma:

```text
fn sum(a:Int,b:Int)->Int = ...
```

Un nombre desconocido es un error de compilación, no una consulta dinámica.

## Inmutabilidad

Los bindings puros se tratan como valores inmutables. Esto simplifica tres propiedades fundamentales:

1. **razonamiento local**: leer `a` dos veces significa leer el mismo valor;
2. **determinismo**: no existe una mutación externa oculta entre ambas lecturas;
3. **identidad semántica**: el programa puede canonicalizarse sin depender de direcciones de memoria del host.

El estado mutable existe en perfiles específicos, pero se expresa mediante contratos de estado/transición, no mutando arbitrariamente un binding puro.

## Expresiones

Una expresión produce un valor tipado. Las familias V2 incluyen, entre otras:

- literales;
- referencia a nombres;
- llamadas de función;
- operadores unarios y binarios;
- `if ... then ... else ...`;
- construcción/acceso de datos;
- `match` exhaustivo;
- folds y bucles acotados;
- expresiones de tareas puras acotadas.

Cada construcción tiene reglas estáticas y un límite operacional. Que una sintaxis sea expresiva no significa que pueda ejecutar código arbitrario del host.

## Orden de evaluación

Los argumentos de una llamada pura se evalúan de forma determinista bajo el contrato del lenguaje. El orden no puede utilizarse como canal oculto para efectos, porque una función pura no posee autoridad observacional o física implícita.

## Identificador de fuente frente a identidad semántica

No todo texto superficial forma parte de la semántica. Espaciado y comentarios pueden cambiar sin alterar el hash semántico cuando la especificación los clasifica como no semánticos. En cambio, cambiar el cuerpo de una función o el valor de entrada sí cambia la identidad correspondiente.

Eso conduce a una distinción útil:

```text
texto fuente
   ↓ parser + normalización semántica
modelo semántico
   ↓ canonicalización
semantic_hash
```

El hash no es un hash ingenuo del archivo tal cual aparece en disco.

## Sombras y colisiones

El compilador evita resoluciones ambiguas. Dos símbolos incompatibles con el mismo nombre, una declaración duplicada o un binding que viole las reglas de scope deben fallar antes de runtime.

En perfiles de estado/efectos, además, un local no puede suplantar silenciosamente un estado o parámetro cuando el contrato lo prohíbe.

## Contrapruebas importantes

- `sum(a, missing)` con `missing` no declarado: falla.
- una llamada con aridad incorrecta: falla.
- un entry cuyo tipo declarado no coincide con el retorno: falla.
- intentar llamar `open(...)`, `eval(...)` o `network.get(...)` como si fueran funciones puras del lenguaje: falla.

La ausencia de ambient authority es deliberada.

## Relación con Total-Core

Total-Core 3.1 da nombres estables a procesos, unidades, labels y relaciones. Las unidades V2 siguen resolviendo sus propios bindings con su autoridad original; V5 no reinterpreta esos nombres.

En el ejemplo, `Calc` es un `unit_id` del proceso padre. `a` y `b` pertenecen a la fuente V2 hija. Son scopes y dominios distintos.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`.
- `tev_script/source_program_v2.py`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md` para `unit`, `invoke_v4` y nombres del proceso padre.
