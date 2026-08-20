# 15 — Aplicación completa: computación + composición + estado

El último capítulo une las piezas principales sin añadir autoridad externa innecesaria. El proceso:

1. parte de un Field con estado `Pending`;
2. ejecuta una unidad V4 pura;
3. ejecuta una unidad V4 recursiva;
4. proyecta ambos receipts al Field mediante bridges;
5. aplica una Transformation raíz `Pending → Complete`;
6. termina en `halt`.

Todo ocurre dentro de un único quantum finito y sin filesystem/red/actuadores.

## Programa raíz

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/main.tevs -->
```tevs
process Tutorial15 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 16;
unit Calc profile pure;
unit Rec profile recursive;
fact Pending = app.pending ["workflow"];
fact Complete = app.complete ["workflow"];
field actual = [Pending];
transform Finish effects bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb resources cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc remove [Pending] add [Complete];
label Start = invoke_v4 Calc result tev.app.calc AfterCalc;
label AfterCalc = invoke_v4 Rec result tev.app.rec Finalize;
label Finalize = apply Finish End;
label End = halt;
entry Start;
```

## Unidad pura

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/calc.tevs -->
```tevs
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

## Unidad recursiva

<!-- tevdoc-source: examples/docs/v31/tutorial/15_complete_application/rec.tevs -->
```tevs
script Rec version "2.0.0";
recursive fn factorial(n:Int)->Int decreases n max_depth 8 = if n==0 then 1 else n*self(n-1);
entry main:Int=factorial(5);
```

El caso documental compila las dos unidades y ejecuta el proceso hasta `HALTED`.

## Paso 1 — Field inicial

Antes de ejecutar:

```text
F0 = { app.pending("workflow") }
```

El Field ya tiene identidad canónica. Los resultados de las unidades todavía no existen.

## Paso 2 — `Calc`

`invoke_v4 Calc` ejecuta el Program IR V4 Pure correspondiente. Su resultado exacto es 5. El runtime crea un bridge fact con relación:

```text
tev.app.calc
```

que liga identidad de unidad, IR y receipt, además del resultado codificado.

Conceptualmente:

```text
F1 = F0 ∪ { tev.app.calc(...) }
```

La adición se realiza mediante una Transformation puente derivada + Apply. Esa bridge Transformation sí queda pinned al `field_hash` observado antes de añadir el fact.

## Paso 3 — `Rec`

La segunda unidad calcula factorial(5)=120 bajo su contrato recursivo acotado. El padre no conoce ni reimplementa el algoritmo; recibe el receipt V4 Recursive.

Después del bridge:

```text
F2 = F1 ∪ { tev.app.rec(...) }
```

## Paso 4 — Transformation raíz

`Finish` elimina `Pending` y añade `Complete`:

```text
F3 = (F2 - { Pending }) ∪ { Complete }
```

Los facts puente permanecen. El workflow cambia de estado sin borrar la evidencia de computación que condujo a él.

Hay una sutileza importante: el statement `transform Finish ...` de la gramática semantic-process actual se compila con `required_before_hash = None`. Por eso los bridge facts añadidos antes de `Finish` no invalidan un pin inexistente. El Apply sigue siendo gobernado: `Pending` debe continuar presente para que `remove [Pending]` sea válido, `Complete` no puede colisionar y el resto del contrato de Transformation se comprueba.

Si construyes una `FieldTransformationV1` por API con un `required_before_hash` exacto, entonces sí debes aplicarla sobre ese snapshot concreto; no es lo que expresa esta source `transform`.

## Paso 5 — Halt

`End` ejecuta `halt`. El quantum termina `HALTED` y produce continuation/checkpoint final marcado como halted.

## Qué identidades intervienen

Hay varias capas y no deben confundirse:

```text
child source semantic hash   Calc / Rec
program_ir_hash              cada V4
unit_hash                    identidad V5 del hijo
source_semantic_hash         modelo fuente Total-Core completo
program_hash                 root V5 ejecutable
field_hash                   snapshot semántico actual
run_receipt_hash             ejecución de cada hijo
continuation/checkpoint hash cierre del quantum
```

La multiplicidad no es burocracia: cada hash responde a una pregunta de identidad distinta.

## Qué ocurre si reordenas las fuentes hijas

El mapping de `unit_sources` es no semántico en su orden. `{Calc, Rec}` y `{Rec, Calc}` deben compilar al mismo programa si contienen los mismos hijos.

Pero intercambiar las instrucciones `invoke_v4` sí cambia el control semántico, porque la tabla de instrucciones preserva orden.

## Qué ocurre si falta una unidad

Si la fuente raíz declara `Rec` pero `unit_sources` sólo contiene `Calc`, el frontend falla con `TEVS_V31_SOURCE_UNIT_SET` antes de construir un programa parcial.

## Qué ocurre si una unidad cambia

Modificar el cuerpo de `Calc` puede cambiar su semantic hash, Program IR hash, unit hash y finalmente `program_hash` del root. El cambio no queda oculto detrás del mismo nombre de archivo.

## Qué ocurre si cambia el estado inicial

Cambiar `Pending`, sus argumentos o el Field inicial cambia las identidades del programa/estado y puede hacer que `Finish` deje de ser aplicable si ya no existe el fact que pretende retirar. No afirmamos que la source `transform` esté pinned por hash, porque el frontend actual no expresa ese pin.

## Qué NO hace esta aplicación

No escribe archivos, no consulta sensores, no llama red y no actúa sobre Unity. Añadir esas operaciones exigiría una unidad/profile/capability/provider apropiados; no se deducen de los hashes `effects/resources` del ejemplo.

## Arquitectura resultante

```text
                    Total-Core V5
        ┌────────────────────────────────┐
        │ Field F0                       │
        │   │                            │
        │   ├─ invoke Calc ─→ V4 Pure    │
        │   │       ↓ receipt/bridge     │
        │   ├─ invoke Rec  ─→ V4 Recursive
        │   │       ↓ receipt/bridge     │
        │   ├─ Apply Finish              │
        │   ↓                            │
        │ Field F3                       │
        │   ↓ halt                       │
        └────────────────────────────────┘
```

Cada caja mantiene una frontera verificable.

## Siguiente paso práctico

A partir de aquí la ruta útil no es aprender más keywords de memoria. Es construir programas pequeños y observar:

- qué queda en fuente;
- qué se convierte en V4;
- qué vive en el root V5;
- qué evidencia produce runtime;
- qué operación necesitaría autoridad externa.

Cuando puedas clasificar esas cinco cosas sin mirar el manual, ya tienes el modelo mental operativo de Total-Core.

## Autoridad técnica

- `spec/TEV_SCRIPT_V2_LANGUAGE.md`.
- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
- `tev_script/source_semantic_process_v3.py`.
- `tev_script/source_total_core_v31.py`.
- `tev_script/runtime_v5_total.py`.
