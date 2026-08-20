# Fronteras del runtime

## Responsabilidad del runtime portable

Un runtime conforme debe:

- aceptar sólo artefactos de schema/profile soportado;
- validar identidad/canonical structure antes de ejecutar;
- respetar bounds;
- producir values/receipts deterministas bajo inputs explícitos;
- registrar observations/effects relevantes;
- fallar cerrado ante ausencia/inconsistencia.

No debe adquirir autoridad ambiental no declarada.

## Lo que NO hace runtime Total-Core

- parsear `.tevs`;
- resolver módulos por red;
- corregir Program IR malformado;
- fabricar proof admissions;
- considerar un effect hash como grant;
- escribir filesystem/red/Unity sólo porque un child describa intent.

## Checkpoint boundary

Runtime trabaja siempre con un `TotalCoreCheckpointV1` válido. El primer checkpoint se deriva del program; los siguientes deben encadenar continuation/state/epoch exactos.

## Instruction loop

Cada quantum ejecuta como máximo `quantum_step_limit`. La máquina dispatcha por kind cerrado:

```text
apply
branch_fact
jump
invoke_v4
halt
```

Unknown kinds ya deberían haber sido rechazados en Program IR validation.

## Child runtime delegation

`invoke_v4` selecciona:

```text
run_program_ir_v4_pure
run_program_ir_v4_recursive
run_program_ir_v4_effects
```

según profile de unidad validado.

El child receipt vuelve como dato; no se comparte el evaluator internamente con V5.

## Bridge boundary

El payload del child se convierte en fact y se añade mediante `field_transformation` + `apply_field_transformation`.

Si el bridge Apply no PASS, V5 falla. No existe «insert fact directamente porque soy runtime».

## Proof boundary

Para proof-open transformation, runtime verifica admission/status/authority y crea una derivación execution-local. El objeto canónico no se muta.

## Observation/effect accounting

Quantum acumula hashes de observations y effects. La continuation liga esos conjuntos junto con resources. Esto evita que una reanudación pierda la historia operacional relevante.

## HALTED frente a SUSPENDED

```text
HALTED    se alcanzó instrucción halt
SUSPENDED se agotó quantum sin halt
```

Ambos producen continuation/next checkpoint; el checkpoint HALTED no puede reanudarse.

## Host IO boundary

Leer/escribir archivos del propio Program IR/checkpoint en CLI es IO de host/tooling. Su error se diferencia de TevScript semantic diagnostics cuando corresponde.

## Provider boundary

Providers materializan capabilities/effects físicos. Deben recibir scope/grant explícito y devolver receipt/estado de commit. El runtime portable no debe importar directamente APIs privilegiadas para saltarse esa frontera.

## Error taxonomy

Mantén separados:

```text
validation error
runtime semantic error
budget/suspension
host IO error
provider/commit error
```

Colapsarlos en una excepción genérica destruye información de gobernanza.

## Recomendación para nuevos runtimes

Implementa primero validator/canonical vectors, después pure execution y sólo después adapters externos. La conformance de semántica no debe depender de tener acceso a filesystem/red real.

## Autoridades

- `tev_script/runtime_v5_total.py`
- `tev_script/program_ir_v5_total.py`
- `tev_script/omega_kernel_v1.py`
- specs de runtime/IR correspondientes.
