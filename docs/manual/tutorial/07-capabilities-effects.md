# 07 — Capabilities, observaciones y efectos

Una de las fronteras más importantes de TEVScript es ésta:

```text
expresar una operación
        ≠
tener autoridad para realizarla
```

El lenguaje puede describir observaciones, estado, comandos o intención de actuar. El mundo externo sólo se toca mediante contratos explícitos del host/provider. Esto evita que una función aparentemente portable gane filesystem, red, reloj o actuadores por accidente.

## Ejemplo base sin autoridad externa

<!-- tevdoc-source: examples/docs/v31/tutorial/07_capabilities_effects/main.tevs -->
```tevs
process Tutorial07 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.capability End;
label End = halt;
entry Start;
```

Esta unidad es `pure`: no puede observar un sensor ni escribir un archivo. Es una base útil porque deja claro que **la ausencia de capability no se rellena con una API del host**.

## Una observación V2 real

La suite de producto usa una fuente effects de esta forma:

```text
script Demo version "2.0.0";
state count:Int=0;
state last:Int=0;
capability observation sensor.read(Int)->Int;
action tick(bias:Int) {
    observe sample=sensor.read(count);
    let next:Int=sample+bias;
    set last=sample;
    set count=next;
    assert count>0;
}
entry main=tick(3);
```

La línea:

```text
capability observation sensor.read(Int)->Int;
```

describe la firma que la unidad puede observar. No contiene un objeto Python, una URL ni un driver concreto.

## Scenario: evidencia externa de ejecución

Una unidad V4 `effects` no puede inventar la respuesta de `sensor.read`. Al construir el artefacto ejecutable, el host aporta un scenario ligado a:

- `capability_table_hash`;
- `capability_id`;
- `contract_hash`;
- argumentos esperados;
- retorno observado/reproducido.

Cambiar el scenario no cambia la semántica de fuente de la unidad, pero sí puede cambiar el Program IR V4 concreto y su resultado de ejecución. Esto separa **programa** de **instancia observacional**.

## `observe`

`observe` adquiere información de una capability declarada. La observación aparece en el transcript/receipt correspondiente. No debe ejecutarse como una llamada oculta al host sin quedar ligada al contrato.

Esta distinción permite replay: una ejecución posterior puede sustituir la observación real por el transcript registrado y verificar que la computación restante coincide.

## Estado local de la unidad effects

En el ejemplo, `count` y `last` son estado de la unidad. `set` actualiza el estado propuesto según la semántica de effects. Ese estado no es el mismo objeto que el `Field` Total-Core padre.

Al volver al padre, `invoke_v4` proyecta el resultado/receipt como un fact puente. No comparte referencias mutables con la unidad.

## Observación no equivale a acción física

Una observación puede tener costes o incluso consecuencias en algunos sistemas reales. Por eso el modelo general no supone que «read» sea mágicamente gratuito/reversible. El contrato de recurso/efecto debe especificarlo cuando importe.

La arquitectura mantiene separadas al menos estas preguntas:

```text
¿es computacionalmente posible?
¿está autorizado?
¿es seguro?
¿hay recursos?
¿es deseable?
```

La última no puede anular las anteriores.

## Comandos e intención

V2 posee una vía posterior para comandos, por ejemplo conceptualmente:

```text
command file.replace(Text,Text);
action publish() {
    request file.replace("out.txt","hello");
}
```

`request` produce intención/plan bajo el contrato correspondiente. No significa que el runtime portable haya escrito ya el archivo. El **commit físico** permanece detrás del provider/grant.

## Total-Core y unidades `effects`

Un proceso 3.1 puede declarar:

```text
unit Sensors profile effects;
```

pero entonces `effect_inputs` debe corresponder exactamente a las unidades `effects` declaradas. Omitir la evidencia requerida o proporcionar inputs para una unidad `pure` falla cerrado.

El schema hijo debe ser exactamente el V4 Effects correspondiente. Un perfil declarado no puede disfrazar un artefacto de otro tipo.

## Filesystem, red y Unity

El mismo principio se aplica a integraciones concretas:

- filesystem: raíz y operaciones scoped;
- red: provider explícito, si existe en el deployment;
- Unity: movimiento/cambio de escena/IO detrás del adaptador autorizado;
- navegador/WASI: sólo capacidades que el host expone deliberadamente.

No hay «ambient authority» por estar ejecutando TEVScript dentro de un proceso que sí tiene esos permisos.

## Fallos esperables

- capability usada pero no declarada;
- scenario sin la capability requerida;
- `contract_hash` que no coincide;
- argumentos/retorno incompatibles con la firma;
- `effect_inputs` con conjunto distinto a las unidades effects;
- intento de llamada host como `open(...)` dentro de código puro;
- tratar un command intent como si fuera receipt de commit físico.

## Regla práctica

Cuando diseñes una operación externa, escribe por separado:

```text
semántica / intención
entrada observacional
capability requerida
autoridad/grant
provider físico
receipt o evidencia de resultado
```

Si dos de esas columnas se han fusionado, probablemente estás ocultando una frontera que TEVScript intenta hacer explícita.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`.
- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`.
- `tev_script/source_effect_program_v2.py`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, sección de effect authority boundary.
