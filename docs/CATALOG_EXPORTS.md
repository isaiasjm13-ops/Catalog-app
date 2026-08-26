# Parser y exportaciones de catálogo

Este bloque porta selectivamente capacidades del prototipo sin incorporar su aplicación, modelos,
SQLite ni upsert. Los módulos son servicios puros y no ejecutan consultas ni escrituras.

## Sugerencias desde nombres

`perfect_catalog.name_parser.parse_product_name()` reconoce algunas marcas, años, motores,
posiciones y referencias OEM. Todo resultado declara `parser_version` y
`review_status=pending_review`; es evidencia propuesta, no una aplicación vehicular aprobada y no
puede activar o publicar un producto.

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
