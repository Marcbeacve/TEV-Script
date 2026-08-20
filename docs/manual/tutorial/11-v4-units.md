# 11 — Unidades Program IR V4

Total-Core no intenta convertir toda computación previa en una nueva máquina V5. En su lugar, incorpora **artefactos Program IR V4 cerrados y validados**. Esta decisión es una frontera de arquitectura: la computación hija conserva su propio contrato y V5 coordina sin reinterpretarla.

## Ejemplo ejecutable

<!-- tevdoc-source: examples/docs/v31/tutorial/11_v4_units/main.tevs -->
```tevs
process Tutorial11 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.tutorial.v4 End;
label End = halt;
entry Start;
```

La fuente de la unidad es:

<!-- tevdoc-source: examples/docs/v31/tutorial/11_v4_units/calc.tevs -->
```tevs
script Calc version "2.0.0";
fn add1(x:Int)->Int=x+1;
entry main:Int=add1(4);
```

El caso documental compila la unidad, construye el root V5 y ejecuta el quantum hasta `HALTED`.

## Del `.tevs` hijo al artefacto V4

La fuente V2 no se ejecuta directamente dentro de Total-Core. La ruta es:

```text
calc.tevs
  ↓ frontend V2
programa semántico V2
  ↓ export/lowering
Program IR V4 Pure
  ↓ validate_program_ir_v4_pure
unidad V5 content-addressed
```

El runtime Total-Core recibe el mapping V4 ya materializado. Nunca vuelve a parsear `calc.tevs` durante ejecución.

## Tres perfiles cerrados

Total-Core admite exactamente:

```text
pure
recursive
effects
```

con correspondencia exacta de schema:

```text
pure      → TEV_SCRIPT_PROGRAM_IR_V4_PURE_V1
recursive → TEV_SCRIPT_PROGRAM_IR_V4_RECURSIVE_V1
effects   → TEV_SCRIPT_PROGRAM_IR_V4_EFFECTS_V1
```

Un perfil declarado y un schema hijo que no coinciden producen `TEVS_V31_TOTAL_UNIT_SCHEMA` o la frontera equivalente de compilación.

## `pure`

Una unidad pura calcula sin autoridad observacional/física implícita. Puede usar el modelo de tipos, funciones, genéricos, colecciones, tareas puras y demás superficie cerrada que su versión admite.

Su receipt expone resultado tipado, representación canónica, hash de resultado y pasos de evaluación.

## `recursive`

Una unidad recursiva conserva el contrato de recursión V2/V4: medida decreciente, profundidad acotada y presupuesto. V5 no cambia `self`, la medida ni la evaluación; sólo llama al runtime V4 Recursive.

## `effects`

Una unidad effects incorpora estado/observaciones y, en perfiles posteriores, intención de command. Requiere evidencia externa (`effect_inputs`) para la instancia concreta. Su receipt puede ligar estado final, transcript de capabilities y observaciones.

Que V5 pueda ejecutar ese artefacto **no concede commit físico**. El provider/grant externo sigue siendo necesario.

## `program_ir_hash`

El IR hijo declara `program_ir_hash`. Al construir `TotalCoreUnitV1`, V5 llama al validador correspondiente y exige que el hash declarado coincida con el artefacto validado.

No se acepta un mapping arbitrario con un string de 64 caracteres puesto a mano.

## `unit_hash`

Una vez validado el hijo, `unit_hash` liga:

```text
schema de unidad
unit_id
profile
program_ir_hash
```

Eso da una identidad estable al hijo **en el contexto del contrato V5**, independiente de la ruta de archivo usada durante build.

## Canonical JSON desacoplado

El mapping V4 se desacopla mediante canonical JSON antes de almacenarse en la unidad. Esto evita que una referencia mutable de Python cambie después de calcular la identidad.

## Validación doble, no duplicada

Hay dos niveles, pero no dos semánticas:

```text
V4 validator → ¿el hijo es un artefacto V4 válido de su perfil?
V5 validator → ¿esta unidad está bien identificada e integrada en el root Total-Core?
```

V5 delega la primera pregunta. DRY aquí es una propiedad de autoridad: la semántica hija tiene un único validador responsable.

## Ejecución de `invoke_v4`

El runtime selecciona el runner por el perfil ya validado. Después del receipt hijo crea un payload puente y lo añade al Field padre mediante una Transformation derivada + Apply.

Para pure/recursive el payload incluye, entre otras identidades:

```text
unit_id
unit_hash
program_ir_hash
run_receipt_hash
result_type
result_encoded
result_hash
evaluation_steps
```

## Límites

Una unidad puede tener su propio presupuesto de evaluación además del presupuesto V5 del quantum. El receipt Total-Core conserva ambos contadores en vez de mezclarlos.

## Errores importantes

- profile no soportado;
- schema V4 distinto al profile;
- `program_ir_hash` manipulado;
- `unit_hash` manipulado;
- dos unidades con igual `unit_id`;
- `invoke_v4` que referencia una unidad desconocida;
- artefacto V4 válido pero aportado como fuente de otra unidad.

## Autoridad técnica

- `spec/TEV_SCRIPT_PROGRAM_IR_V4.md`.
- `tev_script/program_ir_v4.py`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, secciones V4 child units y runtime bridge.
- `tev_script/program_ir_v5_total.py` y `tev_script/runtime_v5_total.py`.
