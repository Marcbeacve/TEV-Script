# Declaraciones, funciones y entry

## Aplicabilidad

Esta página cubre declaraciones de **unidades V2 compatibles** y las declaraciones raíz **Total-Core 3.1** que seleccionan/organizan ejecución.

## Top-level V2

Una unidad pure puede comenzar:

```text
script Demo version "2.0.0";
```

Un módulo V2 usa:

```text
module My.Module version "2.0.0";
```

El script tiene exactamente un entry del perfil que le corresponde. El módulo no tiene entry ejecutable.

## Función pura ordinaria

```ebnf
function-declaration = "fn" , identifier ,
                       "(" , [ parameters ] , ")" , "->" , type ,
                       "=" , expression , ";" ;
```

Ejemplo:

```text
fn add1(x:Int)->Int=x+1;
```

Los parámetros son bindings inmutables. El cuerpo debe producir el retorno declarado.

## Función genérica

```text
generic fn identity<T>(x:T)->T=x;
```

Los parámetros de tipo se cierran mediante especializaciones finitas. El runtime portable no mantiene un «T dinámico» abierto.

Constraints/protocols pueden limitar qué tipos concretos son admisibles.

## Función recursiva

Forma normativa:

```text
recursive fn factorial(n:Int)->Int
    decreases n
    max_depth 8
    = if n==0 then 1 else n*self(n-1);
```

También puede declarar `max_steps`. `decreases` nombra un parámetro `Int`; el self-call debe demostrar descenso bajo el perfil soportado.

La recursión mutua/ambiental no se deriva automáticamente de una llamada normal.

## Parameters

Forma:

```text
name:Type
```

Los nombres son únicos dentro de su scope y el orden de parámetros forma parte de la firma.

## Entry pure

Forma:

```text
entry main:Int=add1(4);
```

El tipo declarado debe coincidir con el resultado de la función/expresión de entry. Un mismatch falla antes de ejecutar.

V2 también admite entry expresional en la superficie definida por su parser, siempre con typecheck.

## Entry effects

Un script de effects usa una action como entry:

```text
entry main=tick(3);
```

No se escribe tipo de retorno pure porque el contrato effects produce estado/receipts bajo otra semántica.

## Records, protocols e impls

V2 top-level también admite:

- `generic record`;
- `protocol`;
- `impl`;
- `generic impl`;
- functions/generic functions/recursive functions.

Un grupo de implementación debe satisfacer exactamente la surface requerida por el protocol y preservar coherence; overlap/ambigüedad falla.

## Imports/exports de módulos

Las declaraciones `import ... as ...` y `export` pertenecen a la superficie de módulos V2. La identidad de módulo no se deriva simplemente de la ruta local; linking está gobernado por IDs/contenido.

## Declaraciones root 3.1

El root no usa `fn` directamente. Sus declaraciones principales son:

```text
process
authority
quantum_steps
fact
field
transform
unit
label
entry
```

`unit` incorpora una computación hija V2→V4. `label` construye control V5.

## `process`

Exactamente un header:

```text
process ProgramId version "3.1.0";
```

## `authority`

Liga un hash de autoridad de 64 hex. Forma parte de la identidad del programa y de la validación de proof admissions. No es un grant físico.

## `quantum_steps`

Entero `1..1_000_000`, obligatorio. Limita las instrucciones V5 por quantum.

## `entry` root

Selecciona un label existente:

```text
entry Start;
```

No es un function call. El compiler resuelve el label a `entry_pc`.

## Cardinalidad y límites V2

Una source unit V2 contiene como máximo 4096 declaraciones. Los IDs/declaraciones deben ser únicos según su namespace/contrato.

## Fallos representativos

- duplicate function/record/unit/header;
- missing entry;
- entry type mismatch;
- unknown type/constraint;
- recursive measure inválida;
- unit child cuyo profile no coincide;
- root entry que apunta a label desconocido.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `tev_script/source_program_v2.py`
- `tev_script/source_effect_program_v2.py`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/source_total_core_v31.py`
