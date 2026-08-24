# Read model de releases publicados

Estado: implementado y validado con datos sintéticos dentro de una transacción PostgreSQL
revertida. No existe todavía un release empresarial publicado.

## Fuente y selección

La API v1.1 usa `catalog_release` como fuente predeterminada. Selecciona únicamente releases con
estado `published` para la marca solicitada y elige el más reciente por fecha de publicación,
creación e ID. Después carga sus items en `item_order`; una consulta nunca mezcla releases.

El modo XLSX sigue disponible solo cuando se indica `--source` o `--source-dir`. Sus identidades
`source-row:*` son provisionales y están rotuladas como tales en JSON y HTML.

## Contrato canónico

Cada item usa `snapshot_schema_version = catalog-product-v1` y exige:

- UUID de producto template y, opcionalmente, UUID de variante;
- referencia interna original y normalizada;
- nombre original y normalizado;
- cantidad disponible numérica o nula;
- `snapshot_sha256` calculado sobre el objeto JSON canónico.

La identidad pública es el UUID de variante cuando existe y, en caso contrario, el UUID del
template. El lector comprueba que esos UUID coincidan con las relaciones de
`catalog_release_item` y rechaza snapshots incompletos, alterados, de una versión desconocida o
con una identidad pública repetida dentro del release.

El release usa `release_hash_algorithm = catalog-release-v2`. Su `snapshot_sha256` cubre definición,
marca, versión, orden, identidades, versión del schema y hash de todos los items. Así se detectan
tanto un cambio de selección como la alteración, eliminación, sustitución o reordenamiento de
productos.

## Ejecución

```powershell
# Fuente publicada predeterminada; solicita la contraseña sin guardarla
.\.venv\Scripts\perfect-catalog-api.exe --brand NATSUKI --prompt-password

# Piloto explícito sobre archivos locales
.\.venv\Scripts\perfect-catalog-api.exe --source-dir data\imports
```

El repositorio de releases es de solo lectura. Crear, inspeccionar, publicar y archivar usa el
workflow separado descrito en [`RELEASE_PUBLICATION_WORKFLOW.md`](RELEASE_PUBLICATION_WORKFLOW.md);
nunca se debe insertar ni marcar un release empresarial como `published` manualmente.

## Garantías verificadas

La integración ejecutada como `perfect_catalog_app` prueba construcción, checksum incorrecto,
publicación, selección, búsqueda, categoría, ficha por UUID, archivo e idempotencia. Los triggers
rechazan la manipulación directa. La transacción se revierte al terminar, por lo que no deja
productos ni releases sintéticos persistidos.
