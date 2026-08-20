# `tev-script conformance`

## Sinopsis

```text
tev-script conformance [--root PATH]
```

## Propósito

Ejecuta la conformance de plataforma 3.1 ligada al checkout indicado. No comprueba un único programa de usuario; valida el conjunto de escenarios/identidades que la plataforma usa como testigo de conformidad.

## Argumentos

No tiene argumentos posicionales.

## Opciones

`--root PATH` selecciona la raíz del repositorio/plataforma que se valida. Por defecto usa el directorio de trabajo actual.

## Entrada aceptada

La raíz debe contener las autoridades, fixtures y superficies que requiere la campaña de conformance actual.

## stdout

Emite un receipt JSON de `run_platform_conformance(root)`.

Los estados principales son:

```text
PASS
HOLD
FAIL
```

`HOLD` conserva incertidumbre/ausencia de evidencia; no se promociona a `PASS`.

## stderr

Los fallos que puedan representarse en el receipt permanecen en la salida estructurada. Un fallo no capturado de infraestructura corresponde a un problema de la herramienta/host.

## Exit codes

```text
0  status = PASS
2  status = HOLD
1  status = FAIL
```

Esta codificación permite distinguir «evidencia todavía insuficiente» de «contrato refutado/roto» en automatización local.

## Ejemplo positivo

```text
tev-script conformance --root .
```

## Ejemplo negativo

Una raíz incompleta o con artefactos de conformance incompatibles no debe producir PASS por usar fixtures disponibles desde otro checkout instalado.

## Versión/perfil

La campaña pertenece a la plataforma actual `3.1.2 / lenguaje 3.1.0 / total_core` y a sus superficies compatibles expresamente incluidas.

## Relacionado

- [`platform-check.md`](platform-check.md)
- `RUN_TEV_SCRIPT_PLATFORM_COMPLETION.py`
