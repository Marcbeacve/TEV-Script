# Field, Transformation y Apply

## Estado del contrato

El cálculo Field/Transformation se desarrolló como capa post-V1. Para Total-Core actual, la autoridad normativa de integración es `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`, que fija como base semántica `Field + Transformation` con `Apply` como juicio operacional. El documento de cálculo conserva el detalle conceptual y no reescribe retroactivamente V1.

## `SemanticFieldV1`

Un Field es una configuración finita, canónica e inmutable de facts. Su identidad incluye:

```text
schema
profile
facts canonicalizados
field_hash
```

El `field_hash` permite verificar identidad del snapshot.

### Lo que no implica

Un Field cuyo fact dice `proved(x)` no demuestra x. Identidad de contenido y autoridad epistémica son dimensiones distintas.

## Fact

Un fact contiene:

```text
relation
arguments
fact_hash
```

La relación es un ID estable y los argumentos datos canónicos. `fact_hash` cubre contenido semántico.

## `FieldTransformationV1`

Una Transformation identifica un delta sobre un Field. Sus componentes relevantes incluyen:

```text
transformation_id
required_before_hash
result_profile
remove_fact_hashes
add_facts
effect_set_hash
resource_vector_hash
proof_requirement_hashes
transformation_hash
```

## `required_before_hash`

Es **opcional en el modelo programático**.

- `None`: la Transformation no está pinned a un `field_hash` concreto; las reglas de remove/add/profile siguen aplicándose sobre el Field que recibe Apply.
- `<64-hex>`: liga la Transformation a un snapshot exacto; otro Field produce rechazo antes de aplicar el delta.

La gramática semantic-process V3/Total-Core 3.1 actual no tiene una cláusula source para este campo. `compile_semantic_process_v3` llama `field_transformation(...)` sin `required_before_hash`, así que los statements `transform ...` de fuente producen `None`.

Los bridge transforms generados por `invoke_v4`, en cambio, sí pasan `required_before_hash=field.field_hash` para fijar el snapshot al que añaden el receipt child.

## Remove/add

`remove_fact_hashes` señala facts que deben estar disponibles para el delta. `add_facts` contiene facts nuevos canónicos. Duplicados/colisiones estructurales se validan según el contrato.

Que `required_before_hash` sea `None` no convierte una eliminación de fact ausente en éxito.

## `result_profile`

Puede conservar o cambiar el profile explícitamente. El cambio de profile forma parte de la identidad de la Transformation.

## Effect/resource identity

`effect_set_hash` y `resource_vector_hash` identifican descripciones relevantes. No son capabilities/grants ni confirman que el efecto físico haya ocurrido.

## Proof requirements

`proof_requirement_hashes` declara evidencia necesaria para admitir la ejecución bajo Total-Core. Un requisito no se considera satisfecho por existir como hash.

También aquí hay que distinguir modelo de source: la statement `transform` del semantic-process actual no expone proof requirements; una Transformation proof-open entra por la superficie programática/IR. La proof admission es siempre externa.

## `transformation_hash`

Se deriva del cuerpo canónico completo. Cambiar precondición opcional, add/remove, effects/resources o proof requirements cambia la identidad.

## Apply

Conceptualmente:

```text
F_before + T
    ↓ validate optional pin, delta and proof state
F_after + ApplyReceipt
```

Un Apply estructuralmente válido produce un nuevo Field; no muta F_before.

Si T tiene `required_before_hash`, se comprueba antes del delta. Después se valida que todos los remove targets existan, que las adiciones no dupliquen facts restantes y que profile/requirements sean coherentes.

## Apply receipt

El receipt liga estado antes/después, transformación y metadata de efecto/recursos bajo el schema correspondiente. Su hash es evidencia de la operación ejecutada por el runtime conforme, no una prueba universal de verdad externa.

## Apply y autoridad física

La relación:

```text
Transformation says "write file"
```

no basta para escribir. La semántica puede representar intent/effect identity, pero commit físico requiere provider/grant.

Por tanto:

```text
Apply semántico ≠ commit físico
```

salvo que un contrato de deployment explícito ligue ambos con receipts apropiados.

## Apply dentro de Total-Core

La instrucción V5 `apply` referencia `transformation_hash`. Al construir el programa se exige que la transformation exista y que sus proof requirements tengan admissions exactas.

En runtime, proof-open Apply crea una transformation execution-local ligada a admissions verificadas; el artefacto canónico original no se modifica.

## Bridge Apply

`invoke_v4` también utiliza este modelo. Tras ejecutar un child receipt, el runtime crea un fact bridge y una Transformation derivada para añadirlo al Field.

La bridge Transformation sí queda pinned al Field observado inmediatamente antes de la proyección. Si el Apply de bridge no cierra como PASS, el runtime falla con `TEVS_V31_RUNTIME_BRIDGE_APPLY`; no inserta el fact por un atajo interno.

## Control por `branch_fact`

El Field resultante puede alimentar control V5. `branch_fact` consulta presencia por `fact_hash`, de modo que el control depende del estado semántico materializado, no de globals ocultos.

## Canonical ordering

En un root Total-Core, transformations se ordenan por `transformation_hash`. El Field/facts sigue su canonicalización propia. Las instrucciones conservan control-flow order.

## Fallos representativos

- Field/fact no canónico;
- `required_before_hash` mal formado o distinto cuando existe;
- remove target ausente;
- transformation hash alterado;
- transformation desconocida en `apply`;
- proof requirement no admitido;
- authority de admission distinta;
- bridge Apply abierto/no PASS.

## Autoridad técnica

- `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`
- `tev_script/omega_semantic_basis_v1.py`
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`
- `tev_script/source_semantic_process_v3.py`
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`
- `tev_script/program_ir_v5_total.py`
- `tev_script/runtime_v5_total.py`
