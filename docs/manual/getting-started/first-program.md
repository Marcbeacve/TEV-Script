# Tu primer programa TEVScript

Esta página usa el lenguaje actual `3.1.0`, perfil `total_core`, mediante la CLI genérica `tev-script`.

El primer programa será deliberadamente pequeño: un proceso con un `Field` vacío que ejecuta un único quantum y termina. No imprime «Hello, world!» porque el núcleo de TEVScript modela **estado semántico + transformaciones + ejecución acotada**; la salida de la CLI es un resultado estructurado de compilación o runtime.

## Código completo

<!-- tevdoc-source: examples/docs/v31/getting_started/01_first/main.tevs -->
```tevs
process FirstProgram version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 1;
field actual = [];
label done = halt;
entry done;
```

Este bloque está ligado al archivo canónico `examples/docs/v31/getting_started/01_first/main.tevs`. Si el bloque y el archivo divergen, la validación documental falla.

## Línea por línea

`process FirstProgram version "3.1.0";` declara un proceso Total-Core y fija explícitamente la versión del lenguaje que interpreta esta fuente.

`authority ...;` fija la identidad de autoridad exigida por el contrato del proceso. En este ejemplo es una identidad sintética estable de 64 dígitos hexadecimales. **No concede por sí sola una capability física**: una autoridad de proceso y un grant de host son contratos distintos.

`quantum_steps 1;` limita cada quantum operacional a un paso. TEVScript no convierte un ciclo abierto en ejecución implícitamente infinita; el runtime avanza mediante quanta finitos.

`field actual = [];` crea el `Field` inicial con perfil `actual` y sin hechos. Un `Field` es estado semántico canónico, no memoria mutable arbitraria del host.

`label done = halt;` define una instrucción que termina el proceso.

`entry done;` selecciona `done` como punto de entrada.

## 1. Comprobar sin escribir un artefacto

Desde la raíz del repositorio:

```text
tev-script check examples/docs/v31/getting_started/01_first/main.tevs
```

El comando debe devolver un objeto JSON con `status: "PASS"`, `language_version: "3.1.0"` y `profile: "total_core"`. `check` valida y compila semánticamente la fuente, pero no escribe Program IR.

## 2. Compilar a Program IR V5

```text
tev-script compile examples/docs/v31/getting_started/01_first/main.tevs --output first-program.json
```

La salida `first-program.json` es el artefacto canónico que consume el runtime actual. La producción no reinterpreta directamente el `.tevs`; ejecuta el IR validado.

## 3. Ejecutar

```text
tev-script run first-program.json
```

El caso documental ejecutable exige:

```text
expected_returncode = 0
expected_status     = HALTED
epochs              = 1
```

El `case.json` asociado compila el programa en un directorio temporal y ejecuta después la ruta pública `tev-script run`. El validador documental no deja el IR generado dentro del árbol del repositorio.

## Qué has aprendido realmente

El programa mínimo ya contiene varias ideas centrales de TEVScript:

```text
fuente versionada
    ↓
Field inicial
    ↓
entry
    ↓
quantum finito
    ↓
halt
    ↓
resultado estructurado
```

A partir de aquí podemos introducir hechos, transformaciones, unidades V4, effects y capabilities sin cambiar esa frontera fundamental.

## Autoridad técnica

La integración de plataforma está definida en `spec/TEV_SCRIPT_3_1_PLATFORM.md`; la semántica Total-Core está definida en `spec/TEV_SCRIPT_V31_TOTAL_CORE.md`; la ruta pública actual está implementada por `tev_script/cli.py` y delega la fuente Total-Core a `tev_script/cli_v31.py`.
