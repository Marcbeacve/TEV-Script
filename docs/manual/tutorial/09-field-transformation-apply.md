# 09 — Field, Transformation y Apply

Ésta es la base semántica del proceso Total-Core. El vocabulario puede parecer abstracto, pero la operación es concreta:

```text
Field antes
  + Transformation
  ──────────────── Apply
        ↓
Field después + receipt
```

`Field` y `Transformation` son las familias semánticas principales. `Apply` es el juicio operacional que relaciona ambas; no se necesita inventarlo como un tercer tipo ontológico independiente.

## Ejemplo ejecutable con verificación posterior

<!-- tevdoc-source: examples/docs/v31/tutorial/09_field_transformation_apply/main.tevs -->
```tevs
process Tutorial09 version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
fact Idle = machine.idle ["M1"];
fact Active = machine.active ["M1"];
field actual = [Idle];
transform Activate effects bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb resources cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc remove [Idle] add [Active];
label Apply = apply Activate Check;
label Check = branch_fact Active Done Missing;
label Done = halt;
label Missing = halt;
entry Apply;
```

El quantum aplica `Activate` y después ejecuta `branch_fact Active ...`. El caso documental exige que la ejecución termine como `HALTED`.

## Field

Un Field es una configuración finita y canónica de facts. Sus propiedades relevantes incluyen:

- inmutabilidad del snapshot;
- perfil explícito, por ejemplo `actual`;
- facts canonicalizados;
- `field_hash` derivado del contenido.

Un Field puede contener una afirmación falsa. El hash prueba identidad del contenido, **no verdad del mundo**.

## Fact

Un fact une una relación estable con argumentos canónicos. En el ejemplo:

```text
machine.idle   ["M1"]
machine.active ["M1"]
```

El nombre fuente (`Idle`, `Active`) resuelve referencias durante compilación; la identidad del fact se liga a su contenido semántico.

## Transformation

`Activate` declara un delta:

```text
remove Idle
add    Active
```

El objeto programático `FieldTransformationV1` puede ligar:

- `required_before_hash` opcional;
- perfil de resultado;
- `effect_set_hash`;
- `resource_vector_hash`;
- requisitos de prueba;
- add/remove de facts.

Es una **descripción identificable de cambio**, no un callback de host.

## Precondición exacta: capacidad del modelo, no keyword de source actual

`FieldTransformationV1` permite `required_before_hash=<field_hash>`. Cuando ese campo no es `None`, Apply exige el snapshot exacto y falla ante estado stale.

La gramática `transform ...` de semantic-process V3/Total-Core 3.1 **no expone actualmente un argumento `required_before_hash`**. `compile_semantic_process_v3` construye esas transformations sin el pin, por lo que `Activate` del ejemplo tiene `required_before_hash = None`.

Eso no vuelve el Apply incondicional: `remove [Idle]` todavía exige que `Idle` exista y las reglas de add/remove/profile siguen validándose. Simplemente hay que distinguir:

```text
source transform actual        → delta sin pin exacto de Field
FieldTransformationV1 por API  → puede incluir required_before_hash
```

## Effect/resource hashes

Los hashes `bbbb...` y `cccc...` del ejemplo son valores sintéticos. Identifican el perfil declarado pero no proporcionan energía, permisos, archivos o dispositivos. TEVScript mantiene separadas **identidad de efecto** y **autoridad de realización**.

## Apply

Apply valida la transformación y produce un nuevo Field/receipt. Un `PASS` significa que el juicio semántico cerró bajo el contrato disponible. No significa por sí mismo que un efecto físico descrito haya sido committed en el mundo.

Para efectos externos, el estado de commit pertenece a capas/provider/receipts adicionales.

## `branch_fact`

Después del Apply, el ejemplo comprueba si `Active` está presente:

```text
branch_fact Active Done Missing
```

La decisión se toma sobre el Field resultante. No consulta una variable global ni repite la operación física. Es control basado en estado semántico ya materializado.

## Canonicalización

El orden de transformations en el root se canonicaliza por `transformation_hash`; el orden de instrucciones no. Los facts del Field también siguen el contrato canónico correspondiente.

Separar orden semántico de orden accidental del contenedor host es esencial para hashes reproducibles.

## Proof-open transformations

Una `FieldTransformationV1` puede llevar `proof_requirement_hashes`. Total-Core sólo admite estructuralmente un `apply` que la use cuando existe una `VerifiedProofAdmissionV1` exacta para cada requisito y la autoridad coincide.

La fuente semantic-process/3.1 actual tampoco expone proof requirements en su statement `transform`; las proof-open transformations pertenecen a la superficie programática/IR. Y, en cualquier caso, la fuente nunca fabrica la admisión: es evidencia externa inyectada por build/integrador.

## Bridge de `invoke_v4`

Cuando `invoke_v4` termina, el runtime construye un fact de resultado y una transformación puente derivada. Esa transformación sí fija `required_before_hash` al `field_hash` observado inmediatamente antes del bridge. La proyección se añade usando `Apply`; el runtime no tiene un atajo privilegiado para mutar almacenamiento interno.

Esto hace que el mecanismo de composición y el mecanismo semántico compartan la misma disciplina y, para bridges, evita aplicar el delta sobre otro snapshot.

## Contrapruebas

Deben fallar:

- transformación desconocida;
- target de PC fuera de rango;
- Transformation programática pinned aplicada a un Field con `required_before_hash` distinto;
- remove de un fact que ya no existe;
- proof requirement sin admisión exacta;
- admisión con autoridad diferente;
- IR que cambia el orden canónico de tablas que sí son ordenadas;
- runtime que añade un bridge fact sin el Apply derivado exigido.

## Qué debes recordar

```text
Field          = qué estado semántico tengo
Transformation = qué cambio identificable propongo
Apply          = juicio que intenta cerrarlo
Receipt        = evidencia estructurada de lo ocurrido
```

Ninguno de ellos, aislado, concede autoridad física.

## Autoridad técnica

- `spec/TEV_SCRIPT_SEMANTIC_APPLY_CALCULUS_V0.md`.
- `tev_script/omega_semantic_basis_v1.py`.
- `spec/TEV_SCRIPT_V3_SEMANTIC_PROCESS_SOURCE.md`.
- `tev_script/source_semantic_process_v3.py`.
- `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`.
- `tev_script/program_ir_v5_total.py` y `tev_script/runtime_v5_total.py`.
