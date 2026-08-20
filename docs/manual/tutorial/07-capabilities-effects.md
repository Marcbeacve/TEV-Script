# 07 — Capabilities, observaciones y efectos

Una de las fronteras más importantes de TEVScript es ésta:

```text
expresar una operación
        ≠
tener autoridad para realizarla
```

El lenguaje puede describir observaciones, estado, comandos o intención de actuar. El mundo externo sólo se toca mediante contratos explícitos del host/provider. Esto evita que una función aparentemente portable gane filesystem, red, reloj o actuadores por accidente.

## Ejemplo ejecutable: un child `effects` real

El proceso raíz declara una unidad V4 de perfil `effects` y proyecta su receipt al Field Total-Core:

<!-- tevdoc-source: examples/docs/v31/tutorial/07_capabilities_effects/main.tevs -->
```tevs
process Tutorial07 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile effects;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.capability End;
label End = halt;
entry Start;
```

La unidad hija es fuente V2 Effects R1 y usa una observación tipada real:

<!-- tevdoc-source: examples/docs/v31/tutorial/07_capabilities_effects/calc.tevs -->
```tevs
script Calc version "2.0.0";
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

Este ejemplo ya no se limita a compilar. Su `case.json` ejecuta el quantum Total-Core con un scenario exacto y exige `HALTED`.

## Capability declarada

La línea:

```text
capability observation sensor.read(Int)->Int;
```

describe una firma. No contiene un objeto Python, una URL ni un driver concreto. El child sólo sabe que puede solicitar una observación `sensor.read` con un `Int` y recibir otro `Int`.

La identidad canónica de este contrato en el ejemplo es:

```text
contract_hash = 7d21ba0b6b6ae82d9987eac1b4b514ba4e4ef22039cc72b498b9caa3aa1be26a
```

y la tabla de capabilities que contiene ese único contrato queda ligada por:

```text
capability_table_hash = 78b40fca1cc70fbb34e48f94af75ffbb9af2c7db4918f23a34a0ed7a53af1cd7
```

Esos hashes se derivan del contrato canónico; no son permisos físicos.

## Scenario: evidencia externa de ejecución

La unidad no puede inventar la respuesta de `sensor.read`. El caso documental aporta esta llamada scripted:

```json
{
  "capability_table_hash": "78b40fca1cc70fbb34e48f94af75ffbb9af2c7db4918f23a34a0ed7a53af1cd7",
  "capabilities": [
    {
      "capability_id": "sensor.read",
      "contract_hash": "7d21ba0b6b6ae82d9987eac1b4b514ba4e4ef22039cc72b498b9caa3aa1be26a",
      "calls": [
        {
          "arguments": [{"$int":"0"}],
          "return": {"$int":"10"}
        }
      ]
    }
  ]
}
```

El estado inicial tiene `count=0`, así que la llamada esperada es exactamente `sensor.read(0)`. El scenario devuelve `10`.

Cambiar el scenario no cambia la semántica de fuente de la unidad, pero sí puede cambiar el Program IR V4 concreto, el receipt y el resultado de ejecución. Esto separa **programa** de **instancia observacional**.

## Ejecución paso a paso

Con `bias=3`:

```text
count inicial = 0
sensor.read(0) = 10
sample = 10
next = 10 + 3 = 13
last  = 10
count = 13
assert count > 0  → PASS
```

El child effects termina por tanto con estado semántico equivalente a:

```text
count = 13
last  = 10
```

Su receipt liga, entre otras identidades, el scenario, transcript de capability, estado final y pasos de evaluación.

## `observe`

`observe` adquiere información de una capability declarada. La observación aparece en el transcript/receipt correspondiente. No debe ejecutarse como una llamada oculta al host sin quedar ligada al contrato.

Esta distinción permite replay: una ejecución posterior puede sustituir la observación real por el transcript registrado y verificar que la computación restante coincide.

## Estado local de la unidad effects

`count` y `last` son estado de la unidad V4 effects. `set` actualiza ese estado bajo la semántica del child. Ese estado **no es** el mismo objeto que el `Field` Total-Core padre.

Al terminar `invoke_v4`, el runtime V5 empaqueta el receipt child en un fact con relación:

```text
tev.tutorial.capability
```

y lo añade al Field padre mediante una Transformation puente derivada + `Apply`. El child no recibe una referencia mutable al Field V5.

## Observación no equivale a acción física

El scenario del tutorial es scripted: no demuestra que exista un sensor físico. En un deployment real, obtener una observación puede tener costes o consecuencias. El modelo general no supone que «read» sea mágicamente gratuito o reversible.

La arquitectura mantiene separadas al menos estas preguntas:

```text
¿es computacionalmente posible?
¿está autorizado?
¿es seguro?
¿hay recursos?
¿es deseable?
```

La última no puede anular las anteriores.

## Comandos e intención: Effects R2

V2 posee una vía posterior para comandos, por ejemplo:

```text
command file.replace(Text,Text);
action publish() {
    request file.replace("out.txt","hello");
}
```

Esa sintaxis pertenece a **Effects R2**, no al Effects R1 observation-only que Total-Core admite actualmente como child.

`request` produce intención/plan bajo el contrato R2 correspondiente. No significa que el runtime portable haya escrito ya el archivo. El **commit físico** permanece detrás del provider/grant.

## Frontera current: Total-Core no admite children R2

Esta distinción es operacional, no sólo terminológica. La ruta current:

```text
compile_total_core_v31
    ↓ unit ... profile effects
compile_effect_program_v2
    ↓
Program IR V4 Effects R1
```

usa `compile_effect_program_v2`. Si la fuente hija contiene `command` o `request`, ese compilador falla con:

```text
TEVS_V2_EFFECT_R2_REQUIRED
```

y exige `compile_effect_command_program_v2`, que pertenece a la vía R2 separada.

Además, la unidad V5 current valida el schema Effects R1 admitido; no convierte automáticamente un Program IR R2 command en un child V5 por compartir el nombre `effects`.

Por tanto:

```text
observation capability + scenario R1
    → sí: child Total-Core current

command/request R2
    → no: no es child Total-Core current
    → requiere su pipeline/provider R2 separado
```

Una futura unión R2→Total-Core tendría que definir/admitir explícitamente esa frontera y demostrar conformance. No debe suponerse por analogía.

## Total-Core y unidades `effects`

Un proceso 3.1 puede declarar:

```text
unit Calc profile effects;
```

pero en la implementación current ese perfil se refiere al child **Effects R1**. `effect_inputs` debe corresponder exactamente a las unidades `effects` declaradas. Omitir la evidencia requerida o proporcionar inputs para una unidad `pure` falla cerrado.

El schema hijo debe ser exactamente el Program IR V4 Effects admitido por Total-Core. Un perfil declarado no puede disfrazar un artefacto de otro tipo ni un R2 como R1.

## Contrapruebas

Deben fallar, entre otros:

- capability usada pero no declarada;
- scenario con `capability_table_hash` distinto;
- `contract_hash` distinto;
- llamada scripted con argumentos diferentes a los que produce la acción;
- retorno con encoding/tipo no canónico;
- `effect_inputs` con conjunto distinto a las unidades effects;
- child con `command/request` R2 en `compile_total_core_v31`;
- intento de llamada host como `open(...)` dentro de código puro;
- tratar un command intent como si fuera receipt de commit físico.

## Filesystem, red y Unity

El mismo principio se aplica a integraciones concretas:

- filesystem: `file.read` observacional puede alimentar R1; `file.replace` command pertenece a R2 separado;
- red: provider explícito, si existe en el deployment;
- Unity: movimiento/cambio de escena/IO detrás del adaptador autorizado;
- navegador/WASI: sólo capacidades que el host expone deliberadamente.

No hay «ambient authority» por estar ejecutando TEVScript dentro de un proceso que sí tiene esos permisos.

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
- `tev_script/ir_v4_effects.py`.
- `tev_script/program_ir_v5_total.py`.
- `tev_script/source_total_core_v31.py`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, sección de effect authority boundary.
