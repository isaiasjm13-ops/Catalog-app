# Centro de ingreso protegido

Estado: implementado sobre la consola local del operador. Requiere la migración `0007` y no
autoriza importación, apply, revisión ni publicación de datos empresariales.

## Propósito

El centro de ingreso resuelve la recepción trazable de archivos antes de cualquier procesamiento:

```text
recibir → validar envoltura → cuarentena → perfilar/procesar → dry-run → revisar → aprobar
```

La etapa actual termina en **cuarentena**. No existe una transición automática desde una carga hacia
`data/imports`, tablas de staging, imágenes publicables o paquetes de exportación.

## Puesta en marcha

1. Después de actualizar el proyecto, ejecutar `ACTUALIZAR-SISTEMA.cmd` e introducir la contraseña de `postgres`.
2. Iniciar `INICIAR-REVISOR.cmd` e introducir sólo la contraseña de `perfect_catalog_app`.
3. Copiar en el navegador abierto el código temporal generado en la consola y usar **Ingresar**.

El servidor comprueba que las tablas de ingreso sean legibles antes de escuchar en el puerto 8081.

## Tipos admitidos

| Tipo | Extensiones | Límite por archivo | Validación de recepción |
|---|---|---:|---|
| Datos de Odoo | `.xlsx`, `.csv`, `.tsv` | 128 MiB | estructura XLSX o texto/separador esperado |
| Paquete de imágenes | `.zip` | 2 GiB | ZIP seguro y contenido limitado a imágenes conocidas |
| Manual/especificación | `.pdf` | 256 MiB | cabecera PDF |
| Paquete de InDesign | `.zip` | 2 GiB | ZIP seguro, INDD/IDML/INDT presente y ejecutables bloqueados |

La validación es de **envoltura y cuarentena**, no análisis antivirus ni conformidad semántica. Los
archivos no se ejecutan, extraen ni sirven por HTTP. El equipo debe conservar sus controles EDR o
antivirus habituales.

## Persistencia e inmutabilidad

- Los bytes aceptados quedan content-addressed bajo
  `data/intake/quarantine/objects/<prefijo>/<sha256>` sin usar el nombre recibido como ruta.
- `data/intake` está fuera de Git y debe incluirse en la política local de backup junto con
  PostgreSQL.
- `intake_asset` conserva un objeto por SHA-256; una carga duplicada reutiliza los mismos bytes.
- `intake_submission` conserva cada evento: nombre, tipo, actor, motivo, tamaño, hash, resultado y
  reporte del validador.
- Ambas tablas son append-only mediante trigger; `perfect_catalog_app` sólo recibe `SELECT` e
  `INSERT`, nunca `UPDATE` o `DELETE`.
- Un archivo rechazado conserva metadatos y hash en PostgreSQL, pero sus bytes temporales se borran.

## Controles de archivos

- nombre Unicode normalizado, sin rutas, NUL ni nombres reservados de Windows;
- `Content-Length` obligatorio y límite global antes de analizar multipart;
- un archivo y cuatro campos como máximo, con campos de texto limitados;
- CSRF, `Origin`, sesión local y confirmación explícita;
- SHA-256 calculado mientras se copia a un temporal controlado;
- ZIP sin rutas absolutas/`..`, duplicados normalizados, enlaces simbólicos ni entradas cifradas;
- máximo 50,000 entradas, 50 GiB descomprimidos y relación de compresión limitada;
- movimiento atómico al objeto final y compensación si falla el registro PostgreSQL;
- sin endpoint de descarga, extracción o ejecución en esta etapa.

## Historial

La pantalla pagina 50 eventos, filtra por tipo y resultado, escapa todo texto recibido y muestra:

- estado `quarantined` o `rejected`;
- contenido duplicado;
- SHA-256 completo, tamaño, actor y fecha;
- motivo, tipo detectado, conteos ZIP y causa de rechazo.

Los estados de ingreso no significan que el contenido sea correcto para negocio. El perfilado de
Odoo y el índice de imágenes son etapas posteriores y explícitas, documentadas por separado. La
lectura del manual y el preflight de InDesign siguen pendientes.
