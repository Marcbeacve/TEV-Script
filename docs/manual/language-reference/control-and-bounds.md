# Control de flujo y cotas

TEVScript mantiene una regla transversal: una construcción que puede prolongar computación debe tener una frontera finita verificable en el perfil portable.

## `if` V2

```text
if condición then a else b
```

Condición Bool; ramas tipadas de forma compatible; evaluación lazy de la rama no seleccionada.

## `match` V2

Control por variantes cerradas. Debe ser exhaustivo, sin duplicados y con resultado tipado común.

## `for ... fold` V2

Iteración estructural sobre colección acotada. El máximo de iteraciones se deriva de `List/Array/Set/Map<...,N>`.

No modifica un accumulator por referencia; produce el siguiente valor del fold.

## `while ... max_iterations` V2

```text
while acc:T=initial when condition max_iterations N do body
```

- `N`: `1..4096`;
- condition: Bool;
- body: mismo tipo del accumulator;
- el loop termina al primer false o al agotar N iteraciones.

Un while sin bound no pertenece a la sintaxis portable V2.

## Recursión V2

Sólo en `recursive fn`. El contrato exige:

- measure parameter explícito;
- medida `Int` en la especialización;
- self-call directo bajo el perfil admitido;
- descenso estricto;
- `max_depth` positivo;
- `max_steps` opcional/finito;
- límites estáticos adicionales sobre posición/número de self-calls.

Mutual recursion no se introduce implícitamente.

## Tasks V2

Las tareas son un DAG puro, no threads con memoria mutable compartida. `spawn`/`await` expresan dependencias; join y selección son deterministas.

Límite de tasks del perfil: 4096.

## `within_steps`

Presupuesto local en `1..1_000_000`. Si una expresión necesitaría cruzarlo, falla antes del paso adicional.

## Root V3/3.1: labels

El semantic process usa labels simbólicos. En Total-Core las instrucciones posibles son:

```text
apply
branch_fact
jump
halt
invoke_v4
```

### `apply`

```text
label A = apply Transform B;
```

Aplica una Transformation conocida y continúa en B si el juicio cierra.

### `branch_fact`

```text
label A = branch_fact Fact Present Absent;
```

Consulta presencia del fact exacto en el Field actual y selecciona el label correspondiente.

### `jump`

```text
label A = jump B;
```

Salto explícito a label resuelto.

### `halt`

```text
label A = halt;
```

Finaliza la ejecución del proceso para ese run; el checkpoint sucesor queda halted.

### `invoke_v4` 3.1

```text
label A = invoke_v4 Calc result tev.result B;
```

Ejecuta una unidad hija exacta, proyecta su receipt al Field mediante bridge Apply y continúa en B.

## Resolución de labels

La fuente usa labels simbólicos. El compiler produce una tabla de instrucciones y PCs válidos. Todo target debe quedar en `0..instruction_count-1`.

La tabla de instrucciones **no se reordena en validación**: su orden es semántico. El compilador de semantic-process sí determina un orden canónico a partir de los labels resueltos.

## `quantum_steps`

Todo root 3.1 declara:

```text
quantum_steps N;
```

con `N` en `1..1_000_000`.

El runtime ejecuta como máximo N instrucciones V5 por quantum. Si no alcanza halt:

```text
status = SUSPENDED
```

y produce continuation/checkpoint.

## Ciclos

Los ciclos de labels están permitidos porque el runtime no los convierte en una llamada infinita indivisible. El quantum los corta en la frontera declarada.

## Límites V5

```text
1 <= instruction_count <= 65_536
1 <= quantum_step_limit <= 1_000_000
0 <= entry_pc < instruction_count
```

Cada V4 child puede tener además sus propios bounds de evaluación.

## Fallos representativos

- target label desconocido;
- PC fuera de tabla en IR;
- instruction kind desconocido;
- recursion measure no decreciente;
- depth/step budget agotado;
- while/within_steps fuera de rango;
- checkpoint halted reanudado;
- quantum limit inválido.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/runtime_v5_total.py`
