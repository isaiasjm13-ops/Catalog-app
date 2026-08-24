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
- Migraciones forward-only: 24 tablas en `0001`; ajuste de objetivos futuros en `0002`.
- Al cierre de la segunda etapa: 75 pruebas descubiertas, 73 aprobadas y 2 integraciones
  PostgreSQL omitidas por requerir credenciales interactivas.
- Prueba de humo Uvicorn/FastAPI contra el XLSX real: 893 productos detectados y respuestas JSON.

## Matriz de situación

| Área | Estado | Evidencia y brecha principal |
|---|---|---|
| Perfilado Odoo | Implementado y verificado para las dos muestras | XLSX/CSV/TSV, hashes antes/después, nulos, duplicados y anomalías. Falta exportación completa con IDs/OEM/aplicaciones. |
| Contrato de importación | Parcial verificado | v0.2 conserva raw/normalizado, acepta reordenamiento, opcionales ausentes, columnas nuevas y conteos variables con límite de piloto. Sigue siendo provisional hasta recibir la exportación completa. |
| Dry-run y transacciones | Parcial verificado | Persiste batch, archivo, staging, resultados, issues y plan; comprueba cero escrituras empresariales. `apply` y rollback empresarial no están implementados. |
| Idempotencia/historial | Parcial | Hashes canónicos, duplicado de archivo, planes y constraints existen. Falta aplicación única real, reintentos y plan sucesor por decisión humana. |
| PostgreSQL/migraciones | Implementado y verificado previamente; verificación actual parcial | DDL y pruebas estáticas sólidas; PostgreSQL funciona. Las pruebas reales actuales se omitieron por credenciales interactivas. No hay Alembic/registro automatizado de revisiones. |
| Modelo normalizado | Parcial | Esquema contempla productos, referencias, inventario, medios, vehículos, releases y auditoría. Las tablas empresariales continúan vacías por diseño del dry-run. |
| Imágenes | No implementado salvo clasificación preliminar | Se detecta Base64 presente/ausente sin decodificar. Faltan indexación filesystem, variantes principal/A/B/GEN/empaque, validación, derivados web y reportes de calidad. |
| FastAPI | Implementado en primera etapa, verificado | API v1 de solo lectura, OpenAPI, paginación, categorías, detalle y errores. Fuente provisional XLSX/staging e IDs `source-row:*`; falta read model de releases y autenticación cuando existan rutas admin. |
| Catálogo web | Parcial | Búsqueda por referencia/nombre y filtro de categoría, responsive, ficha y estado vacío. Faltan OEM, aplicaciones, filtros multinivel, imágenes reales y datos publicados. |
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
2. La web provisional lee el XLSX más reciente. Esto es útil para el piloto, pero no debe convertirse
   en el origen publicado ni en una segunda fuente maestra.
3. Las identidades `source-row:*` cambian con la posición del archivo y no sirven para favoritos,
   offline, URLs públicas, cachés ni releases definitivos.
4. El HTML imprimible no equivale a un PDF QUICK automatizado y nunca debe usarse como PRINT.
5. Los estados históricos de documentación pueden inducir a reinstalar o rediseñar componentes que
   ya existen; `HANDOFF.md` y este informe son la referencia operativa vigente.

## Plan ordenado por dependencias

1. **Aprobación y apply seguro:** transición atómica, recalcular hashes/fingerprint, upserts,
   snapshots/auditoría, rollback e idempotencia; no ejecutar sobre datos empresariales sin aprobación.
2. **Releases/read model:** snapshot JSON estable con UUID, versión y checksum para todos los consumidores.
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

## Bloqueos externos exactos

- PDF completo del manual v2.2.
- Exportación Odoo con IDs estables, OEM, referencias cruzadas, FMSI y aplicaciones estructuradas.
- Zona horaria real de Odoo y sistema de fechas Excel 1900/1904.
- Directorio/muestra real de originales de imagen y reglas confirmadas de nombres/roles.
- Plantillas InDesign, nombres reales de estilos/capas/Script Labels y fuentes licenciadas.
- Especificaciones de imprenta para PDF PRINT.
- Credenciales introducidas por el usuario para repetir pruebas PostgreSQL opt-in; nunca deben
  enviarse por chat ni guardarse en el repositorio.
