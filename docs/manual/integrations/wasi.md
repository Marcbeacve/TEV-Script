# Integración WASI

## Estado exacto

El gate WASI actual está etiquetado explícitamente **IR V3 WASI** y usa `TevScript.Core.V3`. Es una integración compatible, no Program IR V5 Total-Core.

## Contrato del gate

El ejecutable requiere `OperatingSystem.IsWasi()` y acepta:

```text
TevScript.V3WasiGate <fresh|restore> <validator-cases.json> <scenario.json> <checkpoint.json>
```

## Modo `fresh`

1. parse strict JSON de fixture/program/scenario;
2. valida Program IR V3;
3. ejecuta conformance;
4. crea runtime V3;
5. invoca evento inicial;
6. captura `TevScriptRuntimeCheckpointV2`;
7. persiste canonical JSON checkpoint.

## Modo `restore`

1. lee checkpoint existente;
2. parsea/valida;
3. `RestoreExact(program)`;
4. continúa ejecución;
5. comprueba evento esperado;
6. declara restart continuation PASS.

## Qué demuestra

- validator/conformance IR V3 en WASI;
- capture/restore checkpoint V2;
- continuidad exacta tras restart;
- strict UTF-8/JSON en el gate correspondiente.

## Qué NO demuestra

- V5 Total-Core en WASI;
- units V4 dentro de root V5;
- proof admissions V5;
- quanta/checkpoints V5 Total;
- sockets/filesystem ambiental más allá de lo que el host/gate reciba.

## Preopens/capabilities

WASI puede proporcionar preopened directories y otras interfaces, pero no forman parte automática de TEVScript. Deben mapearse mediante un provider/capability contract específico.

## Sobre el fixture documental 3.1

`examples/docs/v31/integrations/wasi/` valida source 3.1 en la plataforma current; no es la fixture que certifica el gate WASI IR V3.

## Autoridad

- `runtimes/csharp/TevScript.V3WasiGate/Program.cs`
- `spec/TEV_SCRIPT_IR_V3.md`
- `spec/TEV_SCRIPT_RUNTIME_CHECKPOINT_V2.md`
