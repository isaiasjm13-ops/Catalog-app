# Auditoría provisional frente al objetivo v2.2

Fecha: 2026-08-24
Commit base auditado: `c4a3ed9 Add product detail and print view`

## Alcance y limitación documental

Se revisaron el repositorio completo, Git, configuración, documentación, código Python, pruebas,
migraciones, reportes locales ignorados y metadatos de las dos muestras Odoo. El archivo
`Manual_Desde_Cero_Perfect_Trading_Natsuki_v2.2.pdf` no está en el repositorio, la carpeta del
adjunto ni el perfil accesible del usuario. Solo se recibió el texto detallado del encargo.

Esta matriz usa ese texto como contrato provisional. El estado **bloqueado** del manual significa
que no puede comprobarse correspondencia literal, numeración, anexos, medidas o detalles visuales
que solo existan en el PDF; no impide continuar las etapas deducibles y seguras.

## Evidencia verificada

- Git estaba limpio en `c4a3ed9` antes de modificar.
- Python 3.14.5 y PostgreSQL 18.6; servicio local activo y `localhost:5432` acepta conexiones.
- Muestra maestra: 893 filas, 13 columnas, SHA-256
  `a8921bc428cece3d318de189237384fc2119383febca57fdc9a86d47844407b8`.
- Segunda muestra: 237 filas, 2 columnas, SHA-256
  `e1693b821cfa871961e1c3cfd0c503f6acc06ba44c7eecb0ba8e734132a09a96`.
- Dry-run conservado: 893 filas staged/clasificadas, 893 altas propuestas, 893 snapshots,
  711 medios pendientes, 182 ausentes, 0 escrituras empresariales.
- Migraciones forward-only `0001`–`0004` aplicadas en `perfect_catalog_dev`.
- Al cierre de la cuarta etapa: 103 pruebas descubiertas y 103 aprobadas, incluidas cinco
  integraciones PostgreSQL ejecutadas con credenciales interactivas.
- Dry-run v0.3 posterior: 893 filas, 2,497 items, SHA fuente intacto y 0 escrituras empresariales.
- Prueba de humo Uvicorn/FastAPI contra el XLSX real: 893 productos detectados y respuestas JSON.
- Read model publicado validado como `perfect_catalog_app` con UUID, hashes de item/release y
  rollback; no quedó ningún release sintético persistido.

## Matriz de situación

| Área | Estado | Evidencia y brecha principal |
|---|---|---|
| Perfilado Odoo | Implementado y verificado para las dos muestras | XLSX/CSV/TSV, hashes antes/después, nulos, duplicados y anomalías. Falta exportación completa con IDs/OEM/aplicaciones. |
| Contrato de importación | Parcial verificado | v0.2 conserva raw/normalizado, acepta reordenamiento, opcionales ausentes, columnas nuevas y conteos variables con límite de piloto. Sigue siendo provisional hasta recibir la exportación completa. |
| Dry-run y transacciones | Verificado localmente | Persiste evidencia y comprueba cero escrituras empresariales. Aprobación/apply atómicos fueron validados en PostgreSQL con rol real, datos sintéticos y rollback. |
| Idempotencia/historial | Parcial | Recalcula hashes/fingerprint, bloquea el plan y evita repetir un plan ya aplicado. Falta ensayo concurrente real y plan sucesor por decisión humana. |
| PostgreSQL/migraciones | Implementado y verificado localmente | `0001`–`0004` aplicadas; catálogo, constraints y permisos reales probados. No hay Alembic/registro automatizado de revisiones. |
| Modelo normalizado | Parcial | Esquema contempla productos, referencias, inventario, medios, vehículos, releases y auditoría. Las tablas empresariales continúan vacías por diseño del dry-run. |
| Imágenes | No implementado salvo clasificación preliminar | Se detecta Base64 presente/ausente sin decodificar. Faltan indexación filesystem, variantes principal/A/B/GEN/empaque, validación, derivados web y reportes de calidad. |
| FastAPI | Implementado y verificado | API v1.1 de solo lectura, OpenAPI, paginación, categorías, detalle y errores. Usa el último release publicado por defecto, UUID estable y validación criptográfica; XLSX/`source-row:*` queda como piloto explícito. No existen rutas admin. |
| Catálogo web | Parcial | Búsqueda por referencia/nombre, filtro de categoría, responsive, ficha y estado vacío consumen el mismo release estable. Faltan OEM, aplicaciones, filtros multinivel, imágenes reales y un release empresarial publicado. |
| PWA/offline | No implementado | No existen manifest, iconos, service worker, IndexedDB, paquetes/versiones/checksum, staging atómico, cuota, sincronización ni UI de estado. |
| PDF QUICK | Parcial mínimo | Existe HTML imprimible manual. Faltan plantillas de impresión completas, QR, selección/categoría/cliente, Playwright, caché, manifest/checksum y QA visual renderizado. |
| InDesign premium | No implementado | El modelo de releases y la decisión JSON canónico existen. Faltan paquete autocontenido, CSV/JSON/images/manifest, reportes, Data Merge, `.idjs`, preflight y salidas DIGITAL/PRINT. |
| Seguridad/roles web | No aplicable aún a mutaciones; incompleto para administración futura | El servicio es local y solo lectura. No hay funciones admin expuestas; antes de crearlas se requieren identidad, roles, autorización y pruebas de backend. |
| Pruebas representativas v2.2 | Parcial | Hay reglas de hashes, duplicados, nulos, negativos, Base64 no expuesto, DDL y API. Falta el dataset visual/límite completo, fallos offline, PDF visual, lotes grandes e InDesign preflight. |
| Instalación limpia/documentación | Parcial | README y comandos actuales fueron corregidos. Varios documentos históricos conservan estados viejos y deben rotularse/actualizarse por etapa sin borrar evidencia. |
| Conformidad literal con manual v2.2 | Bloqueado | Falta adjuntar el PDF fuente. |

## Riesgos prioritarios

1. La identidad provisional depende de referencia interna porque las muestras no traen IDs estables
   de Odoo; el contrato no puede declararse definitivo hasta recibir una exportación completa.
2. El launcher local conserva el XLSX más reciente únicamente como piloto explícito. El comando
   instalable usa PostgreSQL publicado por defecto, pero todavía no existe un release empresarial.
3. Las identidades `source-row:*` siguen siendo inestables en el piloto y no deben migrarse a
   favoritos, offline, URLs públicas o cachés; el modo publicado ya usa UUID.
4. El HTML imprimible no equivale a un PDF QUICK automatizado y nunca debe usarse como PRINT.
5. Los estados históricos de documentación pueden inducir a reinstalar o rediseñar componentes que
   ya existen; `HANDOFF.md` y este informe son la referencia operativa vigente.

## Plan ordenado por dependencias

1. **Aprobación y apply seguro:** transición atómica, recalcular hashes/fingerprint, upserts,
   snapshots/auditoría, rollback e idempotencia; no ejecutar sobre datos empresariales sin aprobación.
2. **Releases/read model:** implementado el consumo de snapshot JSON estable con UUID, versión y
   checksum; falta el workflow controlado que construya y publique releases empresariales.
3. **Pipeline de imágenes:** índice no destructivo, roles, validación, hashes, derivados web y reportes.
4. **Catálogo completo y PWA:** búsqueda estructurada, manifest/app shell, paquetes offline,
   IndexedDB, actualización atómica, cuota y sincronización idempotente.
5. **PDF QUICK:** HTML/CSS estable, QR, selección, Playwright, caché/manifest y revisión visual.
6. **InDesign premium:** paquete autocontenido, muestra Data Merge, UXP `.idjs`, preflight,
   PDF DIGITAL y PDF PRINT separados.
7. **Piloto de aceptación:** matriz completa de datos/imágenes/fallos, tablets/laptops, rendimiento,
   documentación desde cero y decisión explícita antes de escalar a 25,000+ referencias.

## Primera etapa ejecutada

Se implementó FastAPI 0.141.1 sobre una interfaz de repositorio sin retirar el visor previo:

- `GET /api/v1/health`;
- `GET /api/v1/products` con búsqueda, categoría, límite y offset;
- `GET /api/v1/products/{fila}`;
- `GET /api/v1/categories`;
- OpenAPI automático y las rutas HTML existentes bajo el mismo servidor Uvicorn;
- consulta PostgreSQL completada para detalle/categorías, aunque el launcher piloto usa XLSX;
- contrato de respuesta que conserva cero, negativos y ausencias;
- error 404 de producto y errores de fuente preparados;
- empaquetado corregido para incluir el lector/perfilador compartido.

La etapa no escribe en Odoo, Excel, staging ni tablas empresariales.

## Segunda etapa ejecutada

El contrato de entrada pasó a `natsuki-empaques-v0.2` y las reglas a `normalization-v0.2`:

- `Nombre` y `Referencia interna` son las únicas columnas críticas de la evidencia actual;
- encabezados conocidos pueden reordenarse o variar en mayúsculas/acentos normalizables;
- columnas opcionales ausentes quedan nulas y se reportan sin inventar valores; una columna de
  imagen no exportada usa `not_exported`, distinto de una celda realmente `absent`;
- columnas nuevas se conservan íntegramente en `raw_values` y se enumeran en los reportes;
- encabezados vacíos o duplicados tras normalizar se rechazan explícitamente;
- el conteo deja de estar fijado a 893 y usa un límite de piloto predeterminado de 5,000 filas;
- XLSX, CSV y TSV registran su tipo de medio correcto.

La muestra real de 237 filas y dos columnas críticas fue leída correctamente. Esta validación no
es un apply y no produjo escrituras en PostgreSQL.

## Tercera etapa ejecutada

Las reglas pasaron a `normalization-v0.3` y se implementó la compuerta transaccional:

- `approve-plan` y `apply-plan` exigen plan, fingerprint de 64 hexadecimales, actor y motivo;
- se recalculan los hashes de cada item, del plan y del fingerprint usando las versiones persistidas,
  y además se exige que coincidan con el código actual;
- se vuelve a verificar el SHA-256 físico del archivo fuente antes de aprobar y antes de aplicar;
- la aprobación y el apply bloquean la fila del plan; el apply usa aislamiento serializable;
- las altas crean producto y referencia interna, y los snapshots conservan ceros y negativos;
- si falla una escritura, toda la transacción revierte y el plan queda reintentable; si ya fue
  aplicado, un reintento devuelve `already_applied` sin duplicar datos;
- `update`, `blocked` y `conflict` se rechazan antes de escribir porque todavía no existe evidencia
  `before_values` suficiente para una actualización empresarial segura;
- la migración `0003` concede solo transiciones de estado por columna y los INSERT necesarios,
  sin conceder DELETE ni modificar datos existentes.

Las migraciones `0003` y `0004` fueron ejecutadas en `perfect_catalog_dev`. La suite completa aprobó
95/95 pruebas en esta etapa: incluyó permisos efectivos, aprobación, alta, snapshot con valores -2/0, auditoría,
reintento idempotente y rollback. Después se repitió el dry-run real de 893 filas con reglas v0.3:
el archivo mantuvo su SHA-256 y las ocho tablas empresariales permanecieron en cero. Ningún plan
empresarial fue aprobado ni aplicado.

## Cuarta etapa ejecutada

Se implementó el read model estable para todos los consumidores de consulta:

- la API v1.1 selecciona únicamente el release `published` más reciente de la marca pedida;
- cada consulta queda encerrada en un release y conserva el orden publicado;
- la identidad pública es el UUID de variante o, si no existe, el UUID de template;
- `catalog-product-v1` exige identidades, referencia, nombre y cantidad tipada;
- el hash de cada snapshot detecta alteraciones de datos y `catalog-release-v1` cubre además marca,
  versión, orden, identidades, schema y conjunto completo de items;
- una versión de schema desconocida, una relación inconsistente o cualquier hash inválido impide
  servir el release;
- `--source` y `--source-dir` mantienen el piloto XLSX de forma explícita, mientras que el comando
  sin fuente usa PostgreSQL publicado por defecto.

La suite completa aprobó 103/103 pruebas, incluidas cinco integraciones PostgreSQL. La integración
del read model creó un release sintético, lo consultó como `perfect_catalog_app`, verificó UUID y
rechazo de manipulación, y revirtió toda la transacción. El dry-run real posterior conservó 893
filas, 2,497 items, SHA de origen intacto y cero escrituras empresariales. Aún no se ha construido ni
publicado un release empresarial.

## Bloqueos externos exactos

- PDF completo del manual v2.2.
- Exportación Odoo con IDs estables, OEM, referencias cruzadas, FMSI y aplicaciones estructuradas.
- Zona horaria real de Odoo y sistema de fechas Excel 1900/1904.
- Directorio/muestra real de originales de imagen y reglas confirmadas de nombres/roles.
- Plantillas InDesign, nombres reales de estilos/capas/Script Labels y fuentes licenciadas.
- Especificaciones de imprenta para PDF PRINT.
