# Arquitectura de validación y certificación

TEVScript usa múltiples gates porque «un test pasó» no demuestra todas las propiedades de una plataforma multi-runtime.

## Capas

```text
unit/focal tests
    ↓
source/IR/runtime regression
    ↓
portable conformance
    ↓
platform identity/tooling gates
    ↓
repository-selected full certification
```

El documentation validator es un **leaf quality gate** adicional; no sustituye ninguna capa semántica.

## Unit/focal tests

Cubren reglas locales: parser, tipos, identity, runtime, errors, negative controls. TDD usa RED→GREEN sobre esta capa antes de campañas largas.

## Conformance

Fixtures/receipts compartidos permiten comparar runtimes. El objetivo es demostrar que implementaciones independientes producen el mismo resultado/canonical bytes para el profile declarado.

Python es referencia, no autoridad única.

## Portable hosts

El repositorio conserva gates para JavaScript, C#, Browser-WASM/WASI y otras superficies según versión. Un PASS Python no autoriza afirmar paridad multihost.

## Platform identity

`spec/TEV_SCRIPT_VERSION_MATRIX.json`, `TEV_SCRIPT_3_1_PLATFORM.md`, `version.py`, descriptor/tooling y tests impiden mezclar:

```text
package 3.1.2
language 3.1.0
immediate package predecessor 3.1.1
archived V31 package 3.1.0
```

## Repository channel

`REPOSITORY_CHANNEL.json` es la política machine-readable que selecciona validaciones causalmente por paths modificados.

En el estado actual:

- docs/metadata → FAST_METADATA;
- `tev_script/**`, tests/examples/etc → portable-core;
- tools/spec/schemas/conformance/runtimes/docs/VALIDATION → full V1 certification.

`full_after_changed_files = 64` obliga full validation para cambios amplios.

## No GitHub Actions autoritativas

La política declara `github_actions=false`. Un workflow remoto puede ser útil en otros contextos, pero no reemplaza la evidencia local exacta requerida por este repo.

## Exact clean candidate

CERTIFY_FULL sólo tiene autoridad sobre el commit/tree exacto que ejecutó la campaña. Si después se modifica un byte, la evidencia ya no certifica el nuevo candidato.

Por eso el orden correcto es:

```text
terminar cambios
→ commit candidato
→ comprobar clean/tree
→ ejecutar campaign
→ fijar receipt ligado al candidato
```

## Documentación executable gate

`tools/validate_documentation_v31.py` comprueba:

1. VERSION_IDENTITY;
2. MANUAL_ROOT;
3. COVERAGE_MANIFEST;
4. INTERNAL_PATHS/final closure;
5. SOURCE_BINDINGS;
6. EXAMPLE_CASES;
7. DIAGNOSTIC_COVERAGE;
8. PUBLIC_SURFACE_COVERAGE;
9. HISTORICAL_CLASSIFICATION.

Todos deben PASS para receipt documental PASS.

## Source bindings

Los fences `tevs` ejecutables deben tener un `tevdoc-source` externo al code fence y coincidir exactamente con el archivo UTF-8. Directivas mostradas dentro de fences de texto se ignoran como sintaxis explicativa.

## Example cases

Cada `main.tevs` bajo `examples/docs/v31` requiere `case.json`. El validator puede:

- `check` compilar;
- `compile` validar compilación;
- `run` ejecutar quanta reales y comprobar HALTED/SUSPENDED;
- verificar diagnostic code de negativos.

## Diagnostic coverage

`DIAGNOSTIC_COVERAGE_V31.json` declara authorities. Families `codes:["*"]` descubren literals current y exigen que cada código aparezca en la página documental. Un código nuevo sin docs rompe el gate.

El alcance es **declarativo, no nominal**: un archivo nuevo llamado `foo_v31.py` no se convierte en autoridad diagnóstica por coincidir con un glob. Sólo los `authority` declarados por `DOCUMENTATION_COVERAGE_V1.json` o `DIAGNOSTIC_COVERAGE_V31.json` participan en el inventario. Si una nueva superficie debe hacer públicos sus diagnósticos, primero debe añadirse explícitamente a esa autoridad documental.

## Public surface coverage

La CLI se inventaría desde llamadas `argparse.add_parser/add_argument`, incluyendo aliases. La API Python se inventaría desde `tev_script.__all__`. El manifest debe coincidir exactamente, sin missing ni ghost entries.

## Final H closure

En `phase=H_COMPLETE`, el validator exige paths finales, absence de placeholders y sets exactos de language constructs, source profiles, IR/runtime profiles, integrations y version domains.

## Historial de evidencia

`docs/VALIDATION.md` conserva receipts/campañas previas y añade comandos current; no se reescribe un PASS histórico como si se hubiera rerun después.

## Estado frente a autoridad

Una fase `H_COMPLETE` del manifest significa cobertura documental estructural cerrada; **no equivale a CERTIFY_FULL dinámico**. La certificación final sigue la política repository channel.

## Autoridades

- `REPOSITORY_CHANNEL.json`
- `docs/VALIDATION.md`
- `tools/validate_documentation_v31.py`
- runners `RUN_*CERTIFY*` y conformance del repo.
