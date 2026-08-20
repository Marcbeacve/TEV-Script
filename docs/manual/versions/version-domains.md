# Dominios de versión en TEVScript

TEVScript no tiene una única versión que describa todas sus capas. El paquete que instalas, el lenguaje que acepta el frontend, el IR que ejecuta el runtime y el formato de checkpoint evolucionan de forma relacionada pero independiente.

## El problema de usar un solo número

Supón que ves `3.1.0`. Ese texto puede designar la versión del lenguaje Total-Core y también un paquete V31 histórico. Sin contexto, no sabes qué contrato estás comparando.

Por eso la compatibilidad se expresa como una relación entre dominios y no como una comparación numérica ingenua.

## 1. Package version

Identifica una distribución instalable concreta del proyecto Python.

En la línea actual:

```text
paquete candidato actual = 3.1.2
predecesor inmediato     = 3.1.1
paquete V31 archivado    = 3.1.0
```

Un patch del paquete puede corregir tooling, packaging, validación o documentación sin cambiar necesariamente la versión del lenguaje.

## 2. Language version

Identifica el contrato de lenguaje fuente.

Actualmente:

```text
language_version = 3.1.0
```

El frontend Total-Core exige esa identidad en el encabezado del proceso. No interpreta `3.1.2` como lenguaje sólo porque exista un paquete `3.1.2`.

## 3. Source profile

Dos fuentes pueden compartir contexto histórico y aun pertenecer a perfiles distintos.

La matriz actual distingue, entre otros:

```text
3.1.0  total_core       current
3.0.0  semantic_process compatible
2.0.0  general_v2       compatible
1.0.0  bounded_v1       historical
```

El perfil determina qué construcciones y qué pipeline semántico son aplicables.

## 4. Linked-program version

V1 posee un artefacto canónico de linked program propio. Esta identidad no debe confundirse con Program IR ni con la versión del paquete.

Un linked program representa el resultado canónico del enlace/semántica de fuente de su línea; el runtime no debe deducir compatibilidad sólo porque otro artefacto tenga un número parecido.

## 5. Program IR version

Program IR es el contrato ejecutable validado por runtimes conformes.

La matriz actual incluye:

```text
IR V5 / total_core
IR V5 / semantic_process
IR V4 / pure
IR V4 / recursive
IR V4 / effects
IR V3 / portable
IR V2 / portable_legacy
```

Dos artefactos con `version = 5` no son automáticamente intercambiables: también importa el schema/perfil exacto.

## 6. Runtime ABI

La ABI define cómo un runtime recibe/produce los objetos de su perfil. Total-Core usa actualmente una ABI identificada como `v5-total-v1`.

Una implementación sólo es conforme para las combinaciones que declara y demuestra. La ausencia de soporte es unsupported/HOLD; nunca se rellena por inferencia.

## 7. Checkpoint version

Un checkpoint es un contrato de estado/reinicio. Su versión no es la del lenguaje.

Por ejemplo, la matriz actual distingue el checkpoint Total-Core `v5-total-checkpoint-v1` y Runtime Checkpoint V2 para IR V3.

Restaurar un checkpoint requiere compatibilidad exacta con el programa/IR y las identidades que el contrato fija. No es una migración arbitraria de cualquier estado a cualquier versión.

## 8. Adapter/provider version

Los adapters y providers viven en la frontera del host. Su versionado puede evolucionar sin cambiar la semántica central.

Una integración de Unity, filesystem o un provider físico debe declarar qué contrato consume. El lenguaje no hereda automáticamente la semántica particular del host.

## Cómo decidir si dos cosas son compatibles

No compares sólo números. Identifica primero:

```text
qué dominio estás comparando
qué schema/perfil tiene el artefacto
qué autoridad declara la relación
qué runtime/entrypoint la soporta
qué validación demuestra esa ruta
```

La autoridad machine-readable para estas relaciones es:

```text
spec/TEV_SCRIPT_VERSION_MATRIX.json
```

Cuando una ruta no aparece o no puede resolverse exactamente, el comportamiento correcto es fallar cerrada en vez de inventar compatibilidad.

## Ejemplo concreto

Estas tres afirmaciones son simultáneamente correctas:

```text
TEVScript package candidate = 3.1.2
TEVScript language          = 3.1.0
archived V31 package        = 3.1.0
```

La primera habla de distribución, la segunda de semántica fuente y la tercera de un artefacto de packaging histórico. El error corregido durante esta documentación consistía precisamente en usar una sola constante para los dos últimos conceptos de packaging: el predecesor inmediato `3.1.1` y el V31 archivado `3.1.0`.