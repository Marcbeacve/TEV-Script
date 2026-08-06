# [ESTADO ACTUAL DEL PROYECTO]

## Progreso

```text
Decisión de autoridad multilenguaje:       CERRADA
Implementación completa del lenguaje:      NO, PREVIEW 0.2
IR portable V2:                            IMPLEMENTADO Y ESQUEMA ESTRICTO
Perfil JSON canónico:                      IMPLEMENTADO CON VECTORES
Carga JSON estricta Python/JavaScript:      PASS
Compilador Python:                         PASS
Runtime Python:                            CONFORMANT_REFERENCE
Runtime JavaScript ES2022:                 CONFORMANT_ES2022_REFERENCE
Runtime C# netstandard2.1:                 CONFORMANT_DOTNET_REFERENCE
Python/JavaScript/C# byte parity:          PASS, 4 ESCENARIOS
C# canonical vectors:                     12 PASS
C# negative boundary campaign:            PASS
Unity Editor 6000.3 host/Core parity:      PASS OBSERVED, 4 ESCENARIOS
Unity host semantic drift:                 NONE OBSERVED
Unity PlayMode/capability adapter:         PENDIENTE
Mono Player:                               PENDIENTE
IL2CPP:                                    PENDIENTE
Browser execution campaign:               PENDIENTE
Lowering causal/general:                   PENDIENTE
Stable release:                            NO
```

## Log de cambios

- El núcleo Python/JavaScript/C# permanece conforme sobre cuatro escenarios y recibos byte-idénticos.
- `TevScript.Core` sigue siendo `netstandard2.1` y no depende de `UnityEngine`.
- Se añadió un paquete UPM propio `com.marcbeacve.tev-script@0.2.0-preview.1`; no se integra dentro de `TEV-LNU-Unity`.
- Los 9 archivos C# del Core incluidos en el paquete Unity son byte-idénticos al Core C# certificado.
- Unity Editor 6000.3.10f1 compiló y ejecutó ese mismo Core y reprodujo byte por byte `player.basic.v1`, `matrix.full.v1`, `player.idle.v1` y `event-chain.v1`.
- Dentro de Unity también pasan 12 vectores canónicos, UTF-8 estricto, tampering semántico y capability fail-closed.
- Gate Unity-1 no prueba PlayMode, capacidades físicas, Mono Player ni IL2CPP; esas fronteras permanecen separadas.

## Hipótesis falsable

Unity puede hospedar el Core C# portable sin redefinir el lenguaje: al compilar la misma fuente del Core dentro del Editor, debe producir exactamente los mismos recibos observables que Python, JavaScript y .NET.

## Tareas

1. Certificar Gate Unity-1 sobre un commit exacto y árbol Git limpio.
2. Publicar el commit Unity Editor sólo después de la certificación limpia.
3. Gate Unity-2: capacidades reales/PlayMode con conversión `Rat -> float` explícita sólo en el borde físico.
4. Certificar Mono Player y después IL2CPP como hosts separados.
5. Ejecutar una campaña separada en navegador real.
6. Registrar lowering hacia `.tev` y `.tevg` sin duplicar sus kernels.

## Verificación

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_FULL_CONFORMANCE=PASS
THREE_RUNTIME_CONFORMANCE=PASS
UNITY_EDITOR_VERSION=6000.3.10f1
UNITY_CORE_SOURCE_IDENTITY=9 PASS
UNITY_CANONICAL_VECTORS=12 PASS
UNITY_CONFORMANCE_SCENARIOS=4 PASS
UNITY_THREE_RUNTIME_REFERENCE_PARITY=PASS
UNITY_HOST_SEMANTIC_DRIFT=NONE_OBSERVED
UNITY_PLAYMODE=NOT_PROBED
UNITY_MONO_PLAYER=NOT_PROBED
UNITY_IL2CPP=NOT_PROBED
STABLE_RELEASE=NO
```
