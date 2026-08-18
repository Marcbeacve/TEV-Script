# `tev-script describe`

## Sinopsis

```text
tev-script describe
```

## Propósito

Devuelve la identidad de la plataforma pública actual y algunas fronteras que no deben inferirse por versión.

## Argumentos y opciones

No acepta argumentos de proyecto ni opciones propias.

## Entrada aceptada

No consume `.tevs`, Program IR, checkpoint ni inputs externos.

## stdout

En éxito escribe un objeto JSON con schema de descripción de plataforma. Entre sus campos actuales están:

```text
package_version
language_version
profile
runtime_source_compilation
implicit_physical_effects
generic_lsp_current_semantics
```

Para el candidato actual:

```text
package_version = 3.1.2
language_version = 3.1.0
profile = total_core
runtime_source_compilation = false
implicit_physical_effects = false
```

`runtime_source_compilation=false` significa que la frontera de runtime de producción no adquiere autoridad para reinterpretar fuente `.tevs`.

`implicit_physical_effects=false` significa que declarar semántica/effects no concede un efecto físico sin la frontera de capability/provider correspondiente.

## stderr

No se espera salida de error en una instalación coherente. Un fallo de infraestructura se trata como error de la herramienta, no como diagnóstico de un programa fuente.

## Exit codes

```text
0  descripción emitida
```

## Ejemplo positivo

```text
tev-script describe
```

Usa este comando después de instalar para distinguir paquete, lenguaje y perfil.

## Ejemplo negativo conceptual

No uses sólo el nombre del wheel o la versión de `pip` para deducir el Program IR o el ABI de runtime. Esos dominios tienen versiones independientes.

## Versión/perfil

Documenta la superficie genérica actual `3.1.2 / 3.1.0 / total_core`.

## Relacionado

- [`version.md`](version.md)
- [`descriptor.md`](descriptor.md)
- [`../versions/current.md`](../versions/current.md)
