# Integración Browser-WASM

## Estado exacto

El Gate 6B actual prueba **C# TevScript.Core portable compatible** en `browser-wasm`. No es un runtime V5 Total-Core Browser-WASM certificado.

## Qué hace Gate 6B

El programa exige `OperatingSystem.IsBrowser()` y después:

1. carga `Player.tevs.ir.json` como recurso embebido;
2. lo parsea con `TevScript.Core`;
3. obtiene la capability ceiling declarada;
4. crea `TevScriptRuntimeHost`;
5. invoca `Player.damage(10)`;
6. exige `health == 90`;
7. comprueba canonical SHA-256;
8. captura snapshot;
9. confirma ausencia de dependencia Unity;
10. marca el gate Browser-WASM.

## Qué demuestra

- el Core compatible puede ejecutarse en browser-wasm bajo ese gate;
- canonical hashing/runtime state del fixture se conserva;
- la dependencia Unity no es necesaria;
- el host es realmente browser según la plataforma .NET/WASM observada.

## Qué NO demuestra

- que `runtime_js_v31/runtime_v5_total.mjs` sea un browser runtime;
- que Program IR V5 Total-Core se ejecute en Browser-WASM;
- DOM/fetch/storage/clock capabilities;
- filesystem POSIX;
- provider físico de UI/network.

## Browser APIs

DOM, `fetch`, Web Storage, timers, WebGPU, etc. son APIs del host. Para convertirse en capacidades TEV necesitan contrato/provider explícito; no se exponen por ambient authority.

## JS current frente a Browser-WASM

El runtime JS V5 current usa un entrypoint Node (`process.stdin/stdout`). Partes de `core.mjs` son módulos ECMAScript, pero eso no es evidencia suficiente para declarar Browser Total-Core. Haría falta un host/browser gate específico que cubra strict input, V4 children, quanta, checkpoints y parity.

## Sobre el fixture documental 3.1

La source de `examples/docs/v31/integrations/browser-wasm/` es un fixture de compilación current, no la carga que ejecuta Gate 6B.

## Autoridad

- `runtimes/csharp/TevScript.BrowserWasmGate/Program.cs`
- `runtimes/csharp/TevScript.Core/README.md`
- evidencia/gates Browser-WASM del repo.
