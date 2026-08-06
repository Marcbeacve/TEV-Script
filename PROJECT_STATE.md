# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Decisión de autoridad multilenguaje:       CERRADA
Implementación completa del lenguaje:      NO, PREVIEW 0.2
IR portable V2:                            IMPLEMENTADO Y ESQUEMA ESTRICTO
Perfil JSON canónico:                      IMPLEMENTADO CON VECTORES
Carga JSON estricta Python/JavaScript:      PASS
Compilador Python:                         PASS
Runtime Python:                            PASS
Runtime JavaScript ES2022:                 PASS
Python/JavaScript byte parity:             PASS, 4 ESCENARIOS
Runtime C# autocontenido:                   SOURCE IMPLEMENTED
Proyecto C# netstandard2.1:                 PREPARADO
Compilación C#:                            HOLD, TOOLCHAIN NO DISPONIBLE
Receipt C# byte parity:                    PENDIENTE
Unity adapter:                             CONTRATO, NO IMPLEMENTADO
Lowering causal/general:                   PENDIENTE
Stable release:                            NO
```

## Log de cambios

- Se añadió una matriz de conformidad que cubre la superficie operacional V0.2.
- Se endurecieron los esquemas de IR, escenario y recibo con Draft 2020-12.
- Se definió `TEV_CANONICAL_JSON_V1` con vectores normativos.
- Se cerró la carga JSON contra claves duplicadas, flotantes, `-0`, UTF-8
  inválido y enteros estructurales fuera del rango portable.
- Se hizo autocontenido el paquete npm, incluidas pruebas, fixtures y runner.
- Se corrigió la decodificación JavaScript para argumentos y resultados
  constantes de cualquier tipo portable.
- Se fijó la salida de archivos en bytes UTF-8 con LF canónico, independiente
  de la traducción de saltos de línea del host.
- Se hizo segura la retransmisión de logs Unicode bajo stdio redirigido CP1252/ASCII.

## Hipótesis falsable

La especificación normativa y el IR pueden permanecer independientes de todos
los lenguajes anfitrión mientras runtimes reemplazables reproducen las mismas
trazas y recibos acotados byte por byte.

## Tareas

1. Compilar `TevScript.Core` en un entorno .NET funcional.
2. Implementar en C# el codec completo del recibo de conformidad.
3. Reproducir los cuatro recibos autoritativos y los vectores canónicos.
4. Ejecutar una campaña separada en navegador real.
5. Añadir el adaptador Unity como consumidor, no como autoridad semántica.
6. Registrar lowering hacia `.tev` y `.tevg` sin duplicar sus kernels.

## Verificación

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CONFORMANCE_SCENARIOS=4 PASS
STRICT_JSON_INPUT_BOUNDARY=PASS
JSON_SCHEMA_VALIDATION=PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
DETERMINISTIC_UTF8_LF_OUTPUT=PASS
REDIRECTED_STDIO_UNICODE=PASS
CSHARP_PORTABLE_STATIC_BOUNDARY=PASS
CSHARP_COMPILE=HOLD
```
