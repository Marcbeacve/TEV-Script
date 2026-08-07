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
Unity Editor 6000.3 host/Core parity:      PASS CERTIFICADO, 4 ESCENARIOS
Unity host semantic drift:                 NONE OBSERVED
Unity PlayMode capability ABI:             PASS OBSERVED, 3 TESTS
Unity Rat/float physical boundary:         EXPLICIT_AUDITED_PASS
Unity provider authority:                  EXPLICIT_PASS
Unity Input System device:                 NO PROBADO
Unity Animator Controller:                 NO PROBADO
Mono Player:                               PENDIENTE
IL2CPP:                                    PENDIENTE
Browser execution campaign:               PENDIENTE
Lowering causal/general:                   PENDIENTE
Stable release:                            NO
```

## Log de cambios

- El núcleo Python/JavaScript/C# permanece conforme sobre cuatro escenarios y recibos byte-idénticos.
- Gate Unity-1 permanece certificado en `5438da66d407bf9f7ed306cf8a3208189a19fdb7`; Gate Unity-2 lo reejecuta desde un clone aislado con rama efímera para impedir contaminación desde capas superiores.
- El nuevo ensamblado `Marcbeacve.TevScript.Unity` depende de `Marcbeacve.TevScript.Core`; el Core no se modifica y mantiene `noEngineReferences=true`.
- Unity PlayMode 6000.3.10f1 ejecutó tres tests y validó `input.move2d`, `motion.move2d`, `animation.play`, `time.delta` y `debug.log`.
- `motion.move2d` actuó sobre un `Transform` real. Las dependencias/provider authority se suministran explícitamente; el adapter no descubre autoridad mediante `Find*`, `GameObject.Find` o `GetComponent`.
- La frontera física convierte `float -> Rat` representando exactamente el valor IEEE-754 observado. La conversión `Rat -> float` expone bits, racional resultante y error exacto de redondeo; NaN/Infinity fallan cerrado.
- `animation.play` se valida como ABI/sink Unity explícito, sin reclamar todavía un Animator Controller real.
- Input System físico, Animator Controller, Mono Player e IL2CPP permanecen gates separados.

## Hipótesis falsable

El mismo Core portable puede gobernar efectos Unity reales mediante el ABI de capabilities sin adquirir dependencias de Unity ni introducir efectos implícitos. Toda pérdida de exactitud al cruzar entre `Rat` y `float` debe quedar confinada y observable en el adapter físico.

## Tareas

1. Certificar Gate Unity-2 sobre un commit exacto y árbol Git limpio.
2. Publicar el commit PlayMode y actualizar la PR Draft sólo después de la certificación limpia.
3. Certificar un Player Mono como host separado.
4. Certificar IL2CPP/AOT como host separado.
5. Añadir providers opcionales para Input System y Animator sin convertirlos en requisitos del lenguaje.
6. Ejecutar una campaña separada en navegador real.
7. Registrar lowering hacia `.tev` y `.tevg` sin duplicar sus kernels.

## Verificación

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_FULL_CONFORMANCE=PASS
THREE_RUNTIME_CONFORMANCE=PASS
UNITY_EDITOR_VERSION=6000.3.10f1
UNITY_GATE1_REGRESSION=PASS_ISOLATED_CERTIFIED_BASE
UNITY_PLAYMODE_TESTS=3 PASS
UNITY_CAPABILITY_INPUT_MOVE2D=PASS
UNITY_CAPABILITY_MOTION_TRANSFORM2D=PASS
UNITY_CAPABILITY_ANIMATION_PLAY=PASS
UNITY_CAPABILITY_TIME_DELTA=PASS
UNITY_CAPABILITY_DEBUG_LOG=PASS
UNITY_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS
UNITY_PROVIDER_AUTHORITY=EXPLICIT_PASS
UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED
UNITY_ANIMATOR_CONTROLLER=NOT_PROBED
UNITY_MONO_PLAYER=NOT_PROBED
UNITY_IL2CPP=NOT_PROBED
STABLE_RELEASE=NO
```
