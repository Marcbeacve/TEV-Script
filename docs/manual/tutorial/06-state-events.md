# 06 — Estado, hechos y transiciones

Hasta ahora las unidades puras calculaban valores y el proceso padre casi no tenía estado. Total-Core cambia el foco: el estado semántico del proceso se expresa como un `Field` inmutable y las modificaciones admisibles como `Transformation`.

La idea importante es que **estado** no significa «un objeto mutable cualquiera». Cada snapshot tiene identidad canónica y cada transición declara de forma explícita qué facts elimina, cuáles añade y qué metadata de efecto/recursos la identifica. El modelo programático completo puede además fijar un `required_before_hash` exacto; la gramática semantic-process V3/3.1 actual no expone esa cláusula y compila sus transforms con ese campo en `None`.

## Ejemplo ejecutable: `Idle → Running`

Este capítulo ya no usa una unidad hija de conveniencia. El programa raíz 3.1 declara dos hechos y aplica una transformación real.

<!-- tevdoc-source: examples/docs/v31/tutorial/06_state_events/main.tevs -->
```tevs
process Tutorial06 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
fact Idle = state.idle ["machine"];
fact Running = state.running ["machine"];
field actual = [Idle];
transform Activate effects bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb resources cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc remove [Idle] add [Running];
label Start = apply Activate End;
label End = halt;
entry Start;
```

El caso documental ejecuta realmente el quantum y exige `HALTED`.

## `fact`

Un fact posee una relación estable y argumentos representables canónicamente. Aquí:

```text
Idle    = state.idle    ["machine"]
Running = state.running ["machine"]
```

Los nombres `Idle` y `Running` sirven para resolver la fuente. La identidad semántica del hecho se deriva de su contenido canónico, no de la dirección de memoria donde Python lo haya construido.

## `field actual = [Idle]`

El `Field` inicial contiene `Idle`. Es una configuración finita e inmutable. «Inmutable» no significa que el proceso nunca cambie: significa que un cambio produce otro Field mediante una operación gobernada, en vez de alterar retrospectivamente el snapshot anterior.

Conceptualmente:

```text
F0 = { Idle }
```

## `transform Activate ...`

La transformación declara que se pretende quitar `Idle` y añadir `Running`:

```text
remove [Idle]
add    [Running]
```

Los campos `effects` y `resources` son hashes explícitos del perfil correspondiente. **No son permisos físicos**. Identifican información del contrato; no conceden acceso a una máquina, archivo o red.

En la fuente semantic-process actual, `Activate` queda **sin pin de Field exacto** (`required_before_hash = None`). Su aplicabilidad dinámica sigue exigiendo que los facts de `remove` existan y que el delta sea válido. Si necesitas una Transformation programática ligada a un snapshot exacto, `FieldTransformationV1` sí soporta `required_before_hash`; no debes fingir que esa opción ya existe como sintaxis `transform` de fuente.

## `apply`

La instrucción:

```text
label Start = apply Activate End;
```

pide aplicar `Activate` y continuar en `End`. El runtime comprueba el contrato de la transformación. En este ejemplo, si `Idle` ya no estuviera en el Field, la eliminación fallaría; para una Transformation programática pinned, un `required_before_hash` distinto también haría fallar Apply.

El resultado conceptual es:

```text
F0 = { Idle }
      │ Apply(Activate)
      ▼
F1 = { Running }
```

F0 y F1 siguen siendo objetos semánticos distintos y auditables.

## Estado V2 frente a Field V5

V2 también tiene una sintaxis de estado dentro del perfil de effects, por ejemplo:

```text
state count:Int=0;
action increment() { set count=count+1; }
```

Ese estado pertenece a una **unidad V2/V4 effects**. El `Field` Total-Core pertenece al proceso V5 padre. No son la misma memoria ni deben fusionarse conceptualmente.

Cuando una unidad V4 termina, Total-Core puede proyectar su receipt al Field padre mediante una transformación puente derivada. El hijo no obtiene permiso para escribir directamente la estructura del padre.

## Eventos

Un evento puede representarse como un hecho o como parte de un receipt/transcript según el perfil. Lo esencial es preservar su identidad, orden causal relevante y procedencia. No debe convertirse en un callback ambiental cuyo significado dependa de qué host lo ejecutó.

Para sistemas externos, además, «ocurrió un evento» y «se produjo un efecto físico» son afirmaciones diferentes. Un evento de intención puede existir aunque el commit externo todavía no se haya realizado.

## Por qué los snapshots son útiles

La representación por Fields permite:

- comparar estado antes/después;
- obtener hashes reproducibles;
- conservar evidencia histórica sin mutarla;
- reanudar procesos con checkpoints ligados a estado;
- usar `required_before_hash` cuando una Transformation construida por API/IR necesita un pin exacto;
- detectar por ausencia de facts un delta que ya no es aplicable.

## Contrapruebas

Una implementación debe rechazar, entre otras cosas:

- una transformación que referencia un fact inexistente;
- el mismo fact en `remove` y `add` cuando el contrato lo prohíbe;
- una Transformation programática pinned cuyo `required_before_hash` no coincide con el Field observado;
- un target de label inexistente;
- un runtime que modifique el Field por fuera de `Apply` y después fabrique el receipt.

## Lo que este ejemplo no demuestra

Los hashes `bbbb...` y `cccc...` son identidades sintéticas. No prueban que exista un actuator, energía disponible o autorización física. El ejemplo demuestra **semántica de estado y transición**, no ejecución de un dispositivo externo.

## Autoridad técnica

- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`: sintaxis de facts/fields/transforms/labels heredada por el frontend Total-Core.
- `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`: modelo Field/Transformation/Apply.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`: integración y ejecución V5 actual.
- `tev_script/source_semantic_process_v3.py`: muestra que la sintaxis `transform` actual no pasa `required_before_hash`.
- `tev_script/omega_semantic_basis_v1.py`: implementación de referencia de Field/Transformation.
