# Integración Unity

## Estado exacto

El contrato Unity V2 integra el **portable C# Core compatible**, no un runtime V5 Total-Core certificado. La documentación current debe conservar esta frontera.

Unity es host/adaptador; no define el lenguaje.

## Assemblies recomendados por el contrato

```text
Marcbeacve.TevScript.Core
Marcbeacve.TevScript.Unity
Marcbeacve.TevScript.Editor
```

El Core no depende de `UnityEngine`; el adapter contiene providers Unity; el Editor maneja import/diagnostics.

## `.tevs` en Editor

El contrato indica que el importer compila source en **Editor** y almacena IR V2 como asset. Python no se incluye en builds Mono/IL2CPP.

Por tanto la runtime build no interpreta source.

## Capabilities mínimas del adapter

```text
input.move2d
motion.move2d
animation.play
time.delta
debug.log
```

Son bindings del host, no keywords del lenguaje.

## Providers de movimiento

`motion.move2d` puede materializarse por providers distintos:

```text
TransformMotion2D
Rigidbody2DMotion
CharacterControllerMotion
```

La selección debe ser explícita en composición/Inspector. El runtime no debe elegir silenciosamente una autoridad física cuando hay varias compatibles.

## Frontera `Rat` ↔ `float`

El contrato Unity audita la pérdida de exactitud:

- `float → Rat`: registra el valor IEEE-754 exacto observado;
- `Rat → float`: registra bits producidos, racional exacto representado por esos bits y error de redondeo;
- NaN/Infinity/no-finite: fallo cerrado.

La conversión es evidencia del adapter, no una redefinición de `Rat` portable.

## Gates Unity existentes

### Gate Unity-1

Host neutrality del C# Core.

### Gate Unity-2

PlayMode capability ABI y numeric boundary con providers explícitos.

### Gate Unity-3

Mono Player StandaloneWindows64; verifica layout/managed runtime y ejecuta witnesses fuera del Editor.

### Gate Unity-4

IL2CPP/AOT como backend independiente; exige `GameAssembly.dll`/metadata IL2CPP y ausencia de Mono runtime layout correspondiente.

## Qué NO certifican esos gates

El contrato lo deja explícito: no certifican un dispositivo Input System físico ni un Animator Controller real. Son fronteras provider-specific aparte.

Tampoco convierten automáticamente el adapter en runtime Total-Core 3.1.

## Integrar lógica current 3.1

Si quieres llevar Total-Core V5 a Unity, necesitas una frontera/runtime V5 soportada y evidenciada para el deployment. No debes pasar un root V5 al Core V2 actual suponiendo compatibilidad por ser C#.

## Sobre el fixture 3.1 documental

`examples/docs/v31/integrations/unity/` prueba que una source 3.1 con una relation `tev.integration.unity` compila en el frontend current. No es un Gate Unity V5.

## Autoridad

- `adapters/unity/UNITY_ADAPTER_CONTRACT_V2.md`
- gates/build scripts Unity del repositorio
- `spec/TEV_SCRIPT_VERSION_MATRIX.json`
