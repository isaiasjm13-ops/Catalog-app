# Parser y exportaciones de catálogo

Este bloque porta selectivamente capacidades del prototipo sin incorporar su aplicación, modelos,
SQLite ni upsert. Los módulos son servicios puros y no ejecutan consultas ni escrituras.

## Sugerencias desde nombres

`perfect_catalog.name_parser.parse_product_name()` v2 reconoce marcas y abreviaturas, rangos de años,
cilindradas, códigos de motor candidatos, posiciones canónicas, FMSI y referencias adicionales. Los
perfiles `perfect`, `pdm` y `generic` conservan procedencia separada: en particular, PDM mantiene el
contenido entre corchetes como referencia candidata y no lo afirma automáticamente como OEM. Cada
aplicación y evidencia declara confianza, versión y `review_status=pending_review`; no puede activar
ni publicar un producto.

El importador Natsuki incorpora este resultado completo a `name_enrichment` dentro del dry-run y del
fingerprint. La aplicación empresarial todavía ignora esas sugerencias: materializarlas en las tablas
vehiculares requiere un workflow humano posterior. `Referencias Adicionales`, cuando existe como
columna dedicada, se conserva con confianza 1.0 como evidencia exacta de la fuente, no como referencia
primaria aprobada.

## Detección tabular

`perfect_catalog.tabular_detection` detecta aliases frecuentes, delimitador y codificación de
CSV/TSV. No altera encabezados, no acepta identidades por sí solo y no reemplaza
`importer.analyze_headers()`. Su salida es sólo una sugerencia para el futuro paso explícito de
promoción desde cuarentena a perfilado/dry-run.

## PDF y PowerPoint

`export_rows_from_release()` exige la definición completa del release y sus items, valida el schema
de cada snapshot, sus hashes individuales y el `snapshot_sha256` agregado antes de producir filas.
`generate_catalog_pdf()` y `generate_catalog_pptx()` consumen esas filas desacopladas y admiten:

- portada y branding básico (`title`, `subtitle`, `primary_color`);
- agrupación por un campo del snapshot (`group_by`);
- diseños de una a tres columnas (`columns_per_row`);
- referencia, nombre, OEM y aplicaciones cuando existen en el snapshot verificado.

Los generadores no leen PostgreSQL, cuarentena, Odoo ni rutas empresariales. La selección y carga
del release corresponde a una capa llamadora autorizada.

## Alcance comercial excluido

El catálogo es de identidad y compatibilidad, no de ventas ni inventario. Moneda, precios, cantidades,
unidad de medida, responsable, etiquetas operativas, favoritos, fechas operativas y miniaturas Odoo
no se normalizan ni se exponen en API/web/PDF/PPTX/InDesign. El XLSX original y su SHA-256 permanecen
como evidencia, pero esos campos no generan plan items. Las imágenes publicables siguen el workflow
separado de ZIP, asociación exacta, aprobación y materialización.
