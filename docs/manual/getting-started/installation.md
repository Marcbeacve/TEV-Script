# Instalación

TEVScript separa la versión distribuida del paquete de la versión del lenguaje. Conviene verificar ambas después de instalar.

## Requisito de Python

El paquete actual declara Python `>=3.11`.

## Opción A — release publicado

El predecesor publicado inmediato del candidato actual es el paquete `3.1.1`:

```text
python -m pip install tev-script-portable-reference==3.1.1
```

Ese paquete usa lenguaje Total-Core `3.1.0`.

## Opción B — checkout del candidato 3.1.2

Para trabajar con el código de esta rama desde un checkout limpio:

```text
python -m pip install .
```

El `pyproject.toml` raíz identifica el paquete candidato `3.1.2`. Este cambio de paquete **no** cambia la versión del lenguaje, que continúa siendo `3.1.0`.

## Verificar la instalación

Primero comprueba la versión del paquete:

```text
tev-script --version
```

En el release publicado debe mostrar `3.1.1`; en el checkout candidato de esta documentación, `3.1.2`.

Después consulta la identidad semántica actual:

```text
tev-script describe
```

La salida estructurada debe distinguir al menos:

```text
package_version
language_version
profile
```

Para el candidato documentado aquí:

```text
package_version  = 3.1.2
language_version = 3.1.0
profile          = total_core
```

## Por qué hacemos dos comprobaciones

`tev-script --version` responde «¿qué paquete estoy ejecutando?». `tev-script describe` responde además «¿qué lenguaje/perfil expone esta superficie actual?». Tratar ambos números como una sola versión fue precisamente una fuente de ambigüedad que el sistema de documentación actual evita explícitamente.

## Siguiente paso

Continúa con [`first-program.md`](first-program.md).
