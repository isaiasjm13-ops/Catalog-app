# Exportación de catálogos publicados

## Desde la consola visual

Con `INICIAR-REVISOR.cmd` activo, abre `http://127.0.0.1:8081/operator/catalogs`.
La pantalla permite, en orden:

1. construir un borrador inmutable desde un plan aplicado y completamente revisado;
2. revisar UUID/checksum y publicar individualmente el borrador;
3. abrir una vista previa HTML limitada, con agrupación y 1-3 columnas;
4. filtrar por texto/campo y organizar hasta dos niveles de agrupación;
5. elegir título, subtítulo, columnas, perfil InDesign y formatos;
6. generar y descargar PDF, PPTX, snapshot InDesign y manifiesto.

La vista previa vuelve a verificar el release completo, calcula el total de todos los grupos y
renderiza como máximo 24 fichas para mantener una respuesta ágil con catálogos grandes. No crea
archivos ni altera datos.

Los archivos quedan bajo `data/exports/catalogs/<release-uuid>/<export-uuid>/`. El navegador
no decide rutas y sólo puede descargar nombres incluidos en el manifiesto de esa exportación.
El manifiesto diferencia `source_item_count` del release y `selected_item_count`; el filtro nunca
modifica el release publicado.

## Desde línea de comandos

El comando `export-catalog` genera entregables únicamente desde un release con estado
`published`. Antes de escribir, vuelve a validar los hashes de cada producto y el checksum
global del release.

```powershell
perfect-catalog export-catalog RELEASE_UUID `
  --output-dir data/exports/catalogs/mi-catalogo `
  --title "Catálogo Natsuki" `
  --subtitle "Edición 2026" `
  --columns 2 `
  --prompt-password
```

Por defecto se generan:

- PDF para distribución e impresión.
- PPTX editable para presentación digital.
- `*.indesign.json`, snapshot UTF-8 estable para el futuro script de InDesign.
- `*.manifest.json`, con release, versión, checksum fuente y SHA-256 de cada entregable.

Se puede repetir `--format pdf`, `--format pptx` o `--format indesign-json` para limitar
la salida. El directorio de destino debe estar vacío; el comando no reemplaza archivos.

## Contrato InDesign v1

El snapshot usa el esquema `perfect-catalog.indesign-snapshot.v1` e incluye:

- identidad, versión y checksum del release publicado;
- opciones neutrales de maquetación;
- productos ordenados exactamente como quedaron congelados en la publicación.

Este JSON es el límite entre datos y maquetación. El siguiente bloque añadirá el script
de plantillas T4, T2, T1, TABLE y SEPARATOR, sin consultar la base de datos directamente
desde InDesign.

## Crear el primer INDD editable

1. En InDesign, abre `Ventana > Utilidades > Scripts`.
2. Ejecuta `indesign/ImportPerfectCatalog.jsx` desde el panel de scripts.
3. Selecciona el archivo `*.indesign.json` generado por `export-catalog`.
4. Elige dónde guardar el `.indd`.

El script v1 crea portada, separadores automáticos por grupo y páginas de producto según
el perfil seleccionado: T4, T2, T1 o TABLE. Guarda en las etiquetas del documento el UUID,
checksum y perfil del release. Si el snapshot contiene rutas relativas seguras de imágenes,
las coloca como enlaces sin modificar los originales.

Al guardar el INDD también crea `*.preflight.json` con imágenes ausentes, índices de fichas
con texto desbordado y fuentes no disponibles. InDesign nunca se conecta directamente a
PostgreSQL.
