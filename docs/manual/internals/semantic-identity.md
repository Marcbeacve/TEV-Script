# Identidad semántica y content addressing

TEVScript usa varios hashes porque distintos objetos responden a preguntas diferentes. «Tiene SHA-256» no significa que todos los hashes sean intercambiables.

## Taxonomía

### Source semantic hash

Identifica el modelo semántico de una fuente después de parsing/resolution/canonicalización. Debe ignorar diferencias declaradas no semánticas como formato/comentarios y cambiar ante cambios semánticos.

### `program_ir_hash`

Identifica un Program IR cerrado de una versión/profile concreto. En V4 puede cambiar aunque la source semantic identity permanezca estable si cambia evidencia de instancia effects.

### `unit_hash`

Identifica la incorporación V5 de un child:

```text
unit_id + profile + program_ir_hash + schema
```

### `program_hash`

Identifica el root Total-Core ejecutable completo: Field, transformations, units, admissions, instructions, limits, authority, etc.

### `fact_hash` / `field_hash`

Identifican contenido semántico de facts y snapshots Field.

### `transformation_hash`

Identifica precondición/delta/effects/resources/proof requirements de una Transformation.

### `instruction_hash`

Identifica el cuerpo canónico de una instrucción V5.

### Receipt hashes

Identifican resultados/evidencia de una operación concreta: child run, Apply, continuation, quantum, conformance, etc.

## Content identity ≠ live entity identity

Un objeto vivo puede conservar un `EntityId` mientras cambia su Field snapshot. Content addressing es apropiado para artefactos/snapshots inmutables; no sustituye identidad persistente de una entidad mutable.

## Qué debe ser no semántico

Según cada spec, ejemplos incluyen:

- whitespace/comments;
- ruta de archivo de build;
- orden de mappings host cuando el contrato canonicaliza por key/hash;
- worker count/scheduling en computación pura determinista.

No se elimina del hash algo sólo porque resulte incómodo: debe existir autoridad que lo declare no semántico.

## Qué debe alterar identidad

Ejemplos:

- cuerpo de función;
- literal de entry;
- type/capacity;
- profile/schema;
- child source/IR;
- proof admission;
- authority;
- control-flow instruction order;
- quantum bound cuando el contrato lo incluye.

## Canonical ordering

Una estructura puede ser semanticamente unordered pero necesitar bytes deterministas. El contrato fija orden de serialización sin convertirlo en orden causal.

Ejemplos Total-Core:

```text
transformations  sorted by transformation_hash
units            sorted by (unit_id, unit_hash)
proof admissions sorted by (requirement_hash, admission_hash)
instructions     NOT sorted; control order preserved
```

## Canonical JSON

Antes del hash se usa representación canónica: keys/valores/encodings cerrados, no `repr()` del host. `allow_nan=False` y modelos exactos evitan estados no portables.

## Detached mappings

Al incorporar mappings externos, V5 puede serializar/deserializar canonical JSON para romper aliasing con objetos mutables Python. El hash no debe cambiar porque alguien mutó una referencia después de construir el artefacto.

## Hash y verdad

```text
hash coincide → contenido coincide bajo el contrato
```

No implica:

```text
fact es verdadero
proof es correcto
sensor dijo la verdad
acción física ocurrió
```

Esas afirmaciones necesitan evidencias/autoridades adicionales.

## Hash y seguridad

SHA-256 protege identidad/integridad bajo supuestos criptográficos, pero no sustituye policy de autorización, firma de provenance, aislamiento del runtime o safe commit.

## Tests de identidad útiles

Para cada objeto content-addressed debe existir al menos:

1. perturbación semántica → hash cambia;
2. perturbación no semántica → hash conserva;
3. tampering del hash embebido → validator rechaza;
4. reorder permitido → canonicaliza igual;
5. reorder semántico → cambia/rechaza.

## Autoridades

- `tev_script/canonical.py`
- specs de value/IR/version específicos
- `tev_script/program_ir_v5_total.py`
- tests de identity de cada generación.
