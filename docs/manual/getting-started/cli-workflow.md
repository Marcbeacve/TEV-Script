# Flujo normal de la CLI

La superficie genérica actual es `tev-script`. Para un proyecto Total-Core 3.1, el flujo normal es:

```text
check
  ↓
compile
  ↓
run
```

Cada paso valida una frontera diferente.

## `check` — validar fuente y composición

```text
tev-script check main.tevs
```

`check` analiza la fuente actual, resuelve los bindings explícitos de unidades/evidencia y construye el programa semánticamente para comprobarlo, pero no escribe Program IR en disco.

Úsalo durante edición y antes de generar artefactos.

Con unidades:

```text
tev-script check main.tevs --unit Calc=calc.tevs
```

Con inputs de effects:

```text
tev-script check main.tevs \
  --unit Effects=effects.tevs \
  --effect-input Effects=effect-input.json
```

## `compile` — producir el artefacto canónico

```text
tev-script compile main.tevs --output program.json
```

La compilación actual produce Program IR V5 Total-Core canónico. Con unidades y evidencia utiliza los mismos argumentos de proyecto que `check`.

`compile` es la frontera entre la fuente `.tevs` y el artefacto que ejecutará producción.

## `run` — ejecutar IR validado

```text
tev-script run program.json
```

`run` recibe Program IR, no fuente. Esta separación es deliberada: el runtime de producción no gana autoridad para reinterpretar `.tevs`.

Por defecto ejecuta un epoch. Puedes pedir más epochs de forma explícita:

```text
tev-script run program.json --epochs 4
```

El runtime sigue siendo acotado: cada epoch ejecuta un quantum finito y el número de epochs solicitado también está limitado por la CLI.

## Checkpoints

Si una ejecución debe continuar más tarde, la CLI puede escribir un checkpoint:

```text
tev-script run program.json --checkpoint-output checkpoint.json
```

El checkpoint está ligado al programa y a su estado canónico. Un checkpoint incompatible o manipulado falla su validación; no se usa como una sugerencia aproximada de estado.

## Resultados estructurados

Los comandos actuales escriben JSON canónico/estructurado. Por ejemplo, un `check` correcto expone identidad de lenguaje, perfil, hash de IR y hash semántico de fuente. Un `run` expone estado de ejecución, hashes de continuación/Field/checkpoint y epochs ejecutados.

Los scripts deben leer campos, no depender del orden visual o de espacios en la serialización.

## Fallos

Los errores de lenguaje Total-Core se representan como diagnósticos estructurados `TEVS_*`. Un fallo de host/IO se distingue de un diagnóstico semántico. La documentación de diagnósticos negativos verificará el código exacto esperado.

## Comandos de inspección

Además del flujo de programa, la superficie genérica incluye:

```text
tev-script --version
tev-script describe
tev-script descriptor
tev-script conformance
tev-script platform-check
```

`--version` informa del paquete. `describe` informa de paquete/lenguaje/perfil y fronteras actuales. `descriptor` devuelve el descriptor Total-Core. `conformance` y `platform-check` son herramientas de validación de plataforma, no sustitutos de `check` sobre un programa concreto.

La referencia exhaustiva de opciones vive en `docs/manual/cli-reference/`.
