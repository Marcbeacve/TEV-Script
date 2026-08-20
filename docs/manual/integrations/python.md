# Integración Python

## Estado

Python tiene dos superficies distintas que deben nombrarse correctamente:

1. **CURRENT Total-Core 3.1** — API pública en `tev_script.__all__`: compile/validate/run del root V5.
2. **COMPATIBILITY Python host V1** — `PythonRuntimeHostV1` para Program IR V3 precompilado.

No confundas `PythonRuntimeHostV1` con el runtime Total-Core.

## API Total-Core current

Símbolos públicos relevantes:

```python
from tev_script import (
    compile_total_core_v31,
    canonical_total_core_program_bytes,
    initial_total_core_checkpoint,
    run_total_core_quantum,
    validate_total_core_program,
    validate_total_core_checkpoint,
    validate_total_core_quantum_result,
)
```

Flujo en memoria:

```python
program = compile_total_core_v31(
    process_source,
    unit_sources={"Calc": calc_source},
)
checkpoint = initial_total_core_checkpoint(program)
result = run_total_core_quantum(program, checkpoint)
```

`result.status` es `HALTED` o `SUSPENDED` según el quantum.

## Ejemplo semántico 3.1

<!-- tevdoc-source: examples/docs/v31/integrations/python/main.tevs -->
```tevs
process IntegrationPython version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.python End;
label End = halt;
entry Start;
```

El ejemplo demuestra la source/current API; no necesita una capability Python.

## Serialización

`canonical_total_core_program_bytes(program)` produce los bytes canónicos del Program IR V5. No serialices dataclasses con `repr()`/`pickle` como sustituto del formato portable si necesitas interoperabilidad.

## Valores Python

Los mappings/listas usados para construir Fields/IR deben ser datos canonicalizables bajo el contrato. Un `dict` arbitrario con objetos, NaN o claves duplicadas en la fuente JSON no es un valor portable válido.

## Python host V1 de compatibilidad

`PythonProgramArtifactV1` acepta **IR V3** validado/canónico. `PythonRuntimeHostV1`:

- no compila source en producción;
- recoge capabilities requeridas del IR;
- exige bindings explícitos;
- rechaza bindings faltantes;
- por defecto rechaza bindings no usados (least authority);
- serializa acceso a una instancia y rechaza concurrencia/reentrancia ambiental;
- permite capture/restore de `RuntimeCheckpointV2`.

Esto es una superficie compatible distinta del root V5.

## Capabilities Python V1

Los providers son callables ligados por `capability_id`. Ser callable no basta: el ID debe estar requerido por el artefacto. El host falla ante missing/unused según policy.

No uses closures/global state Python para introducir semántica adicional que el IR no declara.

## Concurrencia

Una instancia `PythonRuntimeHostV1` usa un lock y rechaza acceso concurrente/reentrante. La política evita introducir un scheduling host implícito fuera de la máquina TEV.

Para Total-Core, la semántica de quanta/children está en `runtime_v5_total.py`; no heredes automáticamente la política de host V1 a menos que el deployment la defina.

## Excepciones

`TevScriptError` representa diagnóstico del contrato. `OSError`, Unicode errors, etc. pertenecen a la frontera host/tooling cuando no se traducen por una capa específica.

No conviertas cualquier excepción Python en `TEVS_*` inventado.

## I/O

La API Total-Core en memoria no concede filesystem. Leer `main.tevs` o persistir `program.json/checkpoint.json` es responsabilidad del host/CLI. Efectos del programa requieren las capabilities/providers correspondientes.

## Autoridad

- `tev_script/__init__.py`
- `tev_script/source_total_core_v31.py`
- `tev_script/runtime_v5_total.py`
- `tev_script/python_host_v1.py` para compatibilidad IR V3.
