# Estado, observaciones, commands y efectos

## Aplicabilidad

La sintaxis ejecutable de esta página pertenece principalmente a **V2 compatible** y tiene dos perfiles evolutivos que no deben fusionarse:

```text
Effects R1  observaciones/estado
Effects R2  añade command/request planning
```

Total-Core 3.1 current puede incorporar una unidad **Effects R1** como child V4. **No incorpora Effects R2** `command/request` como child V5 en la implementación actual.

## Script Effects R1 V2

Forma representativa:

```text
script Demo version "2.0.0";
state count:Int=0;
capability observation sensor.read(Int)->Int;
action tick() {
    observe sample=sensor.read(count);
    set count=sample;
}
entry main=tick();
```

Un script effects no se mezcla con declaraciones pure arbitrariamente. El frontend determina un perfil cerrado.

## `state`

Forma:

```text
state nombre:Tipo=expresión;
```

El tipo debe pertenecer al modelo V2 admitido y el valor inicial debe tipar correctamente. El estado de una ejecución concreta puede ser sustituido por `current_state` externo bajo el contrato de construcción del artefacto, sin reescribir el semantic hash de fuente.

## `capability observation`

Forma:

```text
capability observation qualified.name(T1,T2)->R;
```

Declara una firma de observación. La declaración:

- no contiene el provider físico;
- no concede permisos del SO;
- no inventa un retorno;
- sí forma parte de la tabla/identidad de capabilities de la unidad.

## `action`

Forma:

```text
action nombre(parametros) {
    pasos...
}
```

Los pasos Effects R1 admitidos incluyen observación, bindings locales, actualización de estado y assertions. Effects R2 añade `request` bajo un command table separado.

## `observe`

Forma típica:

```text
observe sample=sensor.read(count);
```

La capability debe existir y la llamada debe coincidir con su contrato. El resultado proviene del scenario/transcript externo de la instancia de ejecución.

## `observe all`

La gramática V2 incluye una forma agrupada para observaciones declaradas. Agrupar observaciones no concede atomicidad física implícita; cualquier semántica de adquisición/orden relevante pertenece al contrato del perfil/provider.

## `let` en action

Permite un binding local tipado para calcular a partir de valores ya disponibles. Un local no puede suplantar silenciosamente un parámetro/estado cuando las reglas de scope lo prohíben.

## `set`

Actualiza el estado propuesto de la unidad effects:

```text
set count=next;
```

La actualización pertenece al modelo del runtime effects; no es una asignación directa a una variable global Python/JS/C#.

## `assert`

Comprueba una condición semántica durante la ejecución/planificación del action. Un assert fallido no debe convertirse en commit parcial inventado.

## Scenario externo

Program IR V4 Effects R1 se materializa con evidencia de ejecución separada de la fuente. El scenario liga, entre otros elementos:

```text
capability_table_hash
capability_id
contract_hash
calls:
    arguments
    return
```

La fuente puede conservar el mismo `semantic_hash` mientras cambia el scenario y, por tanto, el `program_ir_hash` de la instancia ejecutable.

## `current_state`

Puede proporcionar el estado inicial de la instancia effects. Igual que el scenario, no redefine la fuente; es entrada de ejecución materializada.

## Commands — Effects R2

Effects R2 admite declaraciones:

```text
command file.replace(Text,Text);
```

y pasos:

```text
request file.replace("out.txt","hello");
```

Effects R1 rechaza esa sintaxis con:

```text
TEVS_V2_EFFECT_R2_REQUIRED
```

porque requiere `compile_effect_command_program_v2`.

Cuando R2 se usa por su propia ruta, `request` genera **intención/plan de command**, no commit físico automático.

## Total-Core current y R2

`compile_total_core_v31` usa `compile_effect_program_v2` para las units `profile effects`. Por tanto su frontera current es R1 observation-only.

No basta precompilar R2 y llamarlo `effects`: `TotalCoreUnitV1` valida el schema V4 admitido por el perfil current y no transforma un artefacto R2 en R1.

La relación actual es:

```text
Effects R1 + scenario
    → Program IR V4 Effects R1
    → child Total-Core admitido

Effects R2 + command/request
    → pipeline/plan/provider R2 separado
    → no child Total-Core current
```

## Commit físico

En R1, el runtime portable puede producir observaciones registradas y estado final/propuesto. En R2, su ruta separada puede producir además command intents/planes y receipts asociados.

El acto de escribir un archivo, mover un objeto de Unity, hacer una petición de red o accionar hardware pertenece al provider/grant externo.

```text
semántica portable
      ↓ intent/receipt
provider autorizado
      ↓
mundo externo
```

Que exista un command intent R2 no concede al root V5 actual una operación física ni un bridge R2.

## Filesystem

El contrato filesystem define recursos/raíces/operaciones scoped. `file.read` es la observación R1; `file.replace` es un command R2.

Una capability ID no es un resource ID universal: operaciones sobre paths distintos pueden tocar recursos distintos aunque compartan familia de capability.

No se admite escape por `..` cuando la frontera scoped lo prohíbe.

## Estado V2 frente a Field Total-Core

No confundas:

```text
state de una unidad V4 Effects R1
Field del root V5 Total-Core
```

El primero pertenece al receipt hijo. El segundo es el portador semántico del padre. `invoke_v4` proyecta el receipt R1 al Field mediante un bridge gobernado; no comparte memoria mutable.

## `effect_inputs` en Total-Core

Al compilar 3.1, el mapping `effect_inputs` debe contener **exactamente** las unidades declaradas `profile effects`, que en la ruta current son R1:

- effects sin input: rechazo;
- input para pure/recursive: rechazo;
- input con shape inválida: rechazo.

Cada entrada admite los campos cerrados `scenario` y, opcionalmente, `current_state`.

`effect_inputs` no es una vía para introducir command intents R2 en V5.

## Fallos representativos

- capability desconocida;
- llamada con firma incorrecta;
- estado desconocido;
- shadowing prohibido;
- scenario/contract hash incompatible;
- command usado en Effects R1;
- R2 suministrado como si fuera child Total-Core;
- `effect_inputs` faltante/sobrante;
- provider ausente en fase de commit;
- intento de interpretar un intent como confirmación física.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `tev_script/source_effect_program_v2.py`
- `tev_script/source_total_core_v31.py`
- `tev_script/program_ir_v5_total.py`
- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
