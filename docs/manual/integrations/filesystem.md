# Integración filesystem

## Semántica TEVScript
Una operación de archivo es un efecto/capacidad, no una operación pura.

## Adaptador/proveedor
El proveedor scoped resuelve rutas, observa/ejecuta operaciones autorizadas y emite recibos.

## Conversiones
Contenido, metadatos y rutas se normalizan según el contrato; la ruta nativa del host no entra sin validación.

## Capacidades
Concede sólo raíces/operaciones necesarias y conserva la política de no escape.

## No soportado
No se permite acceso global implícito ni `..` para salir del scope.

<!-- tevdoc-source: examples/docs/v31/integrations/filesystem/main.tevs -->
```tevs
process IntegrationFilesystem version "3.1.0";
authority aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa;
quantum_steps 8;
unit Calc profile pure;
field actual = [];
label Start = invoke_v4 Calc result tev.integration.filesystem End;
label End = halt;
entry Start;
```

Autoridad: `spec/TEV_SCRIPT_V2_FILESYSTEM_CAPABILITIES.md`, `tev_script/scoped_filesystem_v2.py`.