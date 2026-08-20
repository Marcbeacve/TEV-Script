# Manual de TEVScript 3.1

Ésta es la documentación de usuario actual de TEVScript. El paquete candidato es `3.1.2`; el lenguaje actual sigue siendo `3.1.0` con perfil `total_core`. El predecesor publicado inmediato del paquete es `3.1.1`; el paquete V31 archivado `3.1.0` pertenece a otro dominio de versión.

TEVScript es un lenguaje/plataforma determinista con valores portables, identidad canónica, fronteras explícitas de capacidad y separación estricta entre semántica del lenguaje, artefactos compilados y efectos del host.

## Ruta de lectura

- **Empezar:** [`getting-started/`](getting-started/)
- **Aprender paso a paso:** [`tutorial/`](tutorial/)
- **Sintaxis y semántica:** [`language-reference/`](language-reference/)
- **API Python:** [`library-reference/`](library-reference/)
- **CLI:** [`cli-reference/`](cli-reference/)
- **Recetas:** [`howto/`](howto/)
- **Hosts e integraciones (current + compatibilidad):** [`integrations/`](integrations/)
- **Diagnósticos estructurados:** [`diagnostics/`](diagnostics/)
- **Pipeline, IR y runtime:** [`internals/`](internals/)
- **Versiones/deprecaciones:** [`versions/`](versions/)
- **Glosario:** [`glossary.md`](glossary.md)
- **FAQ:** [`faq.md`](faq.md)

## Modelo actual

```text
fuente .tevs
   ↓ frontend de su perfil
identidad semántica de fuente
   ↓ lowering/compilación
Program IR V2/V3/V4/V5 canónico
   ↓ validación
runtime acotado
   ↓
Field / resultado / checkpoint / receipt
```

Total-Core 3.1 combina un proceso semántico con unidades Program IR V4 `pure`, `recursive` o `effects`. `Field`, `Transformation` y `Apply` forman la base de transición; `invoke_v4` ejecuta una unidad por identidad y proyecta su recibo al Field. La computación abierta se expresa mediante quanta finitos y continuaciones.

## Autoridad y host

El manual no redefine el lenguaje. La autoridad normativa vive en `spec/`, especialmente `TEV_SCRIPT_3_1_PLATFORM.md`, `TEV_SCRIPT_V31_TOTAL_CORE.md` y `TEV_SCRIPT_VERSION_MATRIX.json`. Si un host convierte un valor, concede filesystem/red, llama a Unity o materializa un efecto físico, esa responsabilidad sigue fuera de la semántica portable salvo que un contrato explícito la admita.

La matriz de [`integrations/`](integrations/) distingue qué hosts ejecutan Total-Core current y cuáles conservan contratos de compatibilidad. La existencia de un adapter o gate histórico no se presenta como soporte V5 si no existe evidencia específica.

## Documentación ejecutable

Los bloques `tevs` ejecutables están ligados a fuentes de `examples/docs/v31/` mediante `tevdoc-source`. `tools/validate_documentation_v31.py` verifica deriva byte-a-byte, ejecuta los `case.json`, compara diagnósticos exactos y comprueba cobertura de CLI, API pública, diagnósticos e inventarios finales.

El estado de cobertura es machine-readable en `DOCUMENTATION_COVERAGE_V1.json`; los diagnósticos V31 tienen además `DIAGNOSTIC_COVERAGE_V31.json`.

Consulta [`documentation-policy.md`](documentation-policy.md) para la jerarquía de autoridad.
