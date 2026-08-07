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
Unity PlayMode capability ABI:             PASS CERTIFICADO, 3 TESTS
Unity Rat/float physical boundary:         EXPLICIT_AUDITED_PASS
Unity provider authority:                  EXPLICIT_PASS
Unity Mono Player Windows x64:             PASS CERTIFICADO
Unity Mono backend identity:               MONO2X + ARTIFACT LAYOUT PASS
Unity Mono Player execution:               EXIT 0 + RUNTIME WITNESSES PASS
Unity IL2CPP Player Windows x64:            PASS OBSERVED LOCAL PRECOMMIT
Unity IL2CPP backend identity:              IL2CPP + AOT ARTIFACTS PASS
Unity IL2CPP Player execution:              EXIT 0 + RUNTIME WITNESSES PASS
Unity Input System device:                 NO PROBADO
Unity Animator Controller:                 NO PROBADO
Browser execution campaign:               PENDIENTE
Lowering causal/general:                   PENDIENTE
Stable release:                            NO
```

## Log de cambios

- Gate Unity-3 está certificado en `79fe95c8847f1d41be18b55d2e386919ffe57e56` y Gate Unity-4 lo reejecuta desde un clone aislado antes de construir el Player AOT.
- El harness Gate-4 vive en `Marcbeacve.TevScript.Gate4.Il2CppPlayer` y referencia explícitamente `Marcbeacve.TevScript.Core` y `Marcbeacve.TevScript.Unity`; el builder vive en una assembly Editor separada.
- Unity 6000.3.10f1 construyó un `StandaloneWindows64` forzando `ScriptingImplementation.IL2CPP`.
- El artefacto IL2CPP contiene `GameAssembly.dll` y `il2cpp_data/Metadata/global-metadata.dat`; `MonoBleedingEdge` permanece ausente, separando la autoridad AOT de la evidencia Mono.
- `TEVScriptIl2CppGate.exe` arrancó fuera del Editor en `-batchmode -nographics`, ejecutó el IR canónico, comprobó estado runtime y atravesó `input.move2d`, Transform `motion.move2d`, `animation.play`, `time.delta` y `debug.log`, y terminó con código 0.
- La frontera `float <-> Rat`, el testigo de redondeo y el fail-closed de no finitos se reprodujeron dentro del Player IL2CPP.
- El Core y el adapter productivo permanecen sin modificaciones; Gate-4 añade sólo harness/build/runner de certificación.
- Input System físico y Animator Controller permanecen providers separados, no requisitos del lenguaje.

## Hipótesis falsable

El mismo paquete TEV Script ya certificado en Editor, PlayMode y Mono Player puede sobrevivir a la conversión IL2CPP/AOT y ejecutarse como Windows Standalone Player nativo, preservando el Core, el ABI de capabilities y la frontera numérica explícita.

## Tareas

1. Certificar Gate Unity-4 sobre un commit exacto y árbol Git limpio.
2. Publicar el commit IL2CPP Player y actualizar la PR Draft sólo después de la certificación limpia.
3. Ejecutar una campaña separada en navegador real.
4. Añadir providers opcionales para Input System y Animator sin convertirlos en requisitos del lenguaje.
5. Registrar lowering hacia `.tev` y `.tevg` sin duplicar sus kernels.
6. Revisar las fronteras restantes antes de declarar una release estable.

## Verificación

```text
PYTHON_TESTS=29 PASS
JAVASCRIPT_TESTS=21 PASS
CONFORMANCE_SCENARIOS=4 PASS
PYTHON_JAVASCRIPT_BYTE_PARITY=PASS
CSHARP_FULL_CONFORMANCE=PASS
THREE_RUNTIME_CONFORMANCE=PASS
UNITY_GATE3_REGRESSION=PASS_ISOLATED_CERTIFIED_BASE
UNITY_IL2CPP_BUILD_PROCESS_EXIT_CODE=0
UNITY_IL2CPP_PLAYER_BUILD_BACKEND=IL2CPP
UNITY_IL2CPP_GAMEASSEMBLY=PASS
UNITY_IL2CPP_GLOBAL_METADATA=PASS
UNITY_IL2CPP_MONO_RUNTIME=ABSENT_PASS
UNITY_IL2CPP_PLAYER_PROCESS_EXIT_CODE=0
UNITY_IL2CPP_PLAYER_CORE_PARSE=PASS
UNITY_IL2CPP_PLAYER_CAPABILITY_ABI=PASS
UNITY_IL2CPP_PLAYER_FLOAT_BOUNDARY=EXPLICIT_AUDITED_PASS
UNITY_IL2CPP_PLAYER_PROVIDER_AUTHORITY=EXPLICIT_PASS
UNITY_INPUT_SYSTEM_DEVICE=NOT_PROBED
UNITY_ANIMATOR_CONTROLLER=NOT_PROBED
STABLE_RELEASE=NO
```
