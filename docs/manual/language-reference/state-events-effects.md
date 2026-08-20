# Estado, observaciones, commands y efectos

## Aplicabilidad

La sintaxis ejecutable de esta página pertenece principalmente a **V2 compatible** y se convierte en Program IR V4 `effects`. Total-Core 3.1 puede incorporar esa unidad, pero conserva una frontera externa para evidencia y commit físico.

## Script effects V2

Forma conceptual:

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

Los pasos effects admitidos por el perfil incluyen familias como observación, bindings locales, actualización de estado y assertions. Perfiles posteriores añaden command intent.

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

Program IR V4 Effects se materializa con evidencia de ejecución separada de la fuente. El scenario liga, entre otros elementos:

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

## Commands

Una vía effects posterior admite declaraciones:

```text
command file.replace(Text,Text);
```

y pasos:

```text
request file.replace("out.txt","hello");
```

El perfil inicial R1 rechaza esa sintaxis con la frontera que exige el compilador R2 correspondiente. Cuando se admite, `request` genera **intención/plan de command**, no commit físico automático.

## Commit físico

El runtime portable puede producir:

- observaciones registradas;
- estado final/propuesto;
- command intents;
- receipts/transcripts.

El acto de escribir un archivo, mover un objeto de Unity, hacer una petición de red o accionar hardware pertenece al provider/grant externo.

```text
semántica portable
      ↓ intent/receipt
provider autorizado
      ↓
mundo externo
```

## Filesystem

El contrato filesystem define recursos/raíces/operaciones scoped. Una capability ID no es un resource ID universal: `file.write(pathA)` y `file.write(pathB)` pueden tocar recursos distintos aunque compartan familia de capability.

No se admite escape por `..` cuando la frontera scoped lo prohíbe.

## Estado V2 frente a Field Total-Core

No confundas:

```text
state de una unidad V4 effects
Field del root V5 Total-Core
```

El primero pertenece al receipt hijo. El segundo es el portador semántico del padre. `invoke_v4` proyecta el receipt al Field mediante un bridge gobernado; no comparte memoria mutable.

## `effect_inputs` en Total-Core

Al compilar 3.1, el mapping `effect_inputs` debe contener **exactamente** las unidades declaradas `profile effects`:

- effects sin input: rechazo;
- input para pure/recursive: rechazo;
- input con shape inválida: rechazo.

Cada entrada admite los campos cerrados `scenario` y, opcionalmente, `current_state`.

## Fallos representativos

- capability desconocida;
- llamada con firma incorrecta;
- estado desconocido;
- shadowing prohibido;
- scenario/contract hash incompatible;
- command usado en perfil que no lo admite;
- `effect_inputs` faltante/sobrante;
- provider ausente en fase de commit;
- intento de interpretar un intent como confirmación física.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`
- `tev_script/source_effect_program_v2.py`
- `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
