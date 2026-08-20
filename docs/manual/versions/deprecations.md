# DEPRECATION y compatibilidad

TEVScript no usa «hay una versión nueva» como sinónimo de «todo lo anterior está deprecated». La matriz distingue **current**, **compatible** e **historical** por dominio.

## Regla

Una superficie sólo debe llamarse deprecated/retirada cuando exista una decisión de autoridad que lo declare. No se infiere de que no aparezca en el tutorial current.

## Estado actual relevante

### Lenguaje

```text
3.1.0 current
3.0.0 compatible
2.0.0 compatible
1.0.0 historical
```

### Program IR

```text
V5 total_core        current
V5 semantic_process compatible
V4 pure/recursive/effects compatible
V3 portable          compatible
V2 portable_legacy   historical
```

### Runtime/checkpoint

El runtime V5 Total-Core es current; runtime IR V3/checkpoint V2 permanecen compatibles.

## Historical ≠ borrable

Una superficie historical puede ser necesaria para:

- reproducir receipts antiguos;
- verificar paquetes publicados;
- migrar datos/proyectos;
- mantener tests de compatibilidad;
- entender lineage de una autoridad.

No debe eliminarse únicamente para simplificar documentación.

## Compatibilidad ≠ recomendación para nuevo root

V2/V3 siguen soportados en roles concretos, pero un usuario que empieza un proceso nuevo debe usar root Total-Core 3.1 salvo requisito de compatibilidad.

## Package versions

Package 3.1.1/3.1.0 son predecessors compatibles/publicados; package 3.0.0/1.0.0 aparecen históricos en la matriz. Esto no determina por sí solo el status de cada language/IR domain.

## Procedimiento para una futura deprecation

Antes de marcar una superficie:

1. actualizar authority/version matrix;
2. documentar replacement/migration;
3. añadir tests de warning/rejection según política;
4. preservar ability de leer/verificar artefactos históricos cuando sea requisito;
5. definir fecha/version donde cambia status;
6. no reutilizar el mismo schema para semántica distinta.

## Qué NO está declarado aquí

Esta página no inventa una lista de keywords deprecated. Si una sintaxis compatible sigue soportada por su version/profile, su ausencia en Total-Core source no la vuelve deprecated.

## Autoridad

- `spec/TEV_SCRIPT_VERSION_MATRIX.json`
- `CHANGELOG.md`
- specs de cada generación.
