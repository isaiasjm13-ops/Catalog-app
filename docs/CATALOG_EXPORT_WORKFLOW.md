# Exportación de catálogos publicados

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

El script v1 crea portada y fichas básicas de dos columnas, guarda en las etiquetas del
documento el UUID y checksum del release, y reporta cuadros con texto desbordado. No
modifica imágenes originales ni conecta InDesign directamente con PostgreSQL.
