# `tev-script --version`

## Sinopsis

```text
tev-script --version
```

## Propósito

Muestra la **versión del paquete ejecutable**, no la versión del lenguaje.

En el candidato documentado por esta rama:

```text
3.1.2
```

El release publicado inmediato es `3.1.1`; ambos exponen lenguaje Total-Core `3.1.0`.

## Argumentos

Ninguno.

## Opciones

`--version` es una opción raíz de `tev-script`.

## Entrada aceptada

No lee fuente, IR, checkpoint ni configuración de proyecto.

## stdout/stderr

En éxito escribe la versión del paquete en `stdout` y termina sin JSON adicional. No debe confundirse con `describe`, que sí devuelve identidad multidominio estructurada.

## Exit code

```text
0  versión mostrada correctamente
```

El manejo concreto de `argparse` puede materializar este resultado como una salida temprana del proceso.

## Ejemplo positivo

```text
tev-script --version
```

Para un checkout del candidato actual, el valor esperado es `3.1.2`.

## Ejemplo de confusión que debe evitarse

No interpretes:

```text
tev-script --version → 3.1.2
```

como:

```text
language_version = 3.1.2
```

El lenguaje actual sigue siendo `3.1.0`.

## Versión/perfil

```text
package candidate = 3.1.2
language          = 3.1.0
profile           = total_core
```

## Relacionado

- [`describe.md`](describe.md)
- [`../versions/version-domains.md`](../versions/version-domains.md)
