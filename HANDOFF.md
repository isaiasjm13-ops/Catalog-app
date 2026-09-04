# HANDOFF.md - Estado de Traspasos Entre Sesiones

## Bloque 2026-09-04 (cont. 6): fotos variantes con sufijo de letra (bug real de la convención)

- El usuario reportó que la galería de fotos nunca aparecía para sus productos reales, aunque
  sí funcionaba en las pruebas. Causa real: su convención de nombres de archivo para fotos
  adicionales usa **letras** (`CKT-507AU-LB A`, `CKT-507AU-LB - A`, `CKT-507AU-LB (A)`, luego
  B, C, D, E, F...), no el sufijo numérico (`-2`, `-3`) que era lo único que reconocía el
  sistema. Todas sus fotos con letra quedaban silenciosamente sin ningún candidato de
  coincidencia — invisibles, no solo sin galería.
- `normalize_image_key` ya colapsaba espacio/guion/paréntesis al mismo `-`, así que las tres
  variantes de escritura del usuario ya normalizaban igual; solo faltaba reconocer la letra
  final. `split_variant_suffix` ahora reconoce también un sufijo de una sola letra: `A` significa
  "foto principal" (igual que no tener sufijo), `B`, `C`, `D`... son fotos adicionales
  (variant_index 2, 3, 4...).
- **Bug que me atrapé a mí mismo antes de terminar**: al hacer que "A" devolviera `None` (para
  tratarse igual que "sin sufijo"), el código que llama a `split_variant_suffix` usaba
  `if suffix is not None` para decidir si intentar la coincidencia — eso habría ignorado
  silenciosamente el caso "A" (su valor SÍ es None). Se corrigió comparando `base_key !=
  lookup_key` en su lugar, que distingue correctamente "no se reconoció ningún sufijo" de
  "se reconoció un sufijo que resulta en la foto principal". Las pruebas nuevas cubren
  exactamente este caso para que no vuelva a pasar inadvertido.
- Algoritmo de coincidencia subido a `exact-approved-reference-v3` (migración `0027`, mismo
  patrón de `DROP CONSTRAINT IF EXISTS`/`ADD CONSTRAINT` que 0026 para poder re-ejecutarse; v1
  y v2 se conservan porque ya hay candidatos reales generados con esas versiones).
- Verificación: 377 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
- Pendiente: aplicar la migración 0027 (`ACTUALIZAR-SISTEMA.cmd`) contra la base real, y volver
  a intentar con una foto real de letra (ej. `CKT-507AU-LB B.jpg`) para confirmar que ahora sí
  genera un candidato y, una vez aprobada, aparece en la galería del HTML autónomo.

## Bloque 2026-09-04 (cont. 5): resto de la lista de mejoras ("haz todo")

- **Migración 0026 corregida**: el archivo ya aplicaba todo su DDL pero le faltaba insertar su
  propia fila en `schema_migration`; se corrigió (ver bloque de más abajo, "Corrección
  posterior") y se hizo cada sentencia re-ejecutable con `IF NOT EXISTS`/`DROP ... IF EXISTS`
  para el caso de reintento con el esquema ya aplicado.
- **Aviso cuando no hay perfil de marca que vincular**: en Marcas, si la Company todavía no
  tiene ningún `brand_profile`, el desplegable de "Vincular perfil" salía vacío sin explicación
  (así lo reportó el usuario con una marca real, EXACTCARS). Ahora muestra un aviso claro
  indicando crear uno primero en "Añadir una marca".
- **Registro vehicular**: se agregó Perodua (130 marcas / 156 alias en total).
- **Historial de exportaciones sin recorrer todo el disco cada vez**: `list_operator_catalog_exports`
  ahora lee un índice de solo-anexar (`_export_index.jsonl`) que cada exportación real
  (`create_operator_catalog_export`) actualiza en el momento; solo la primera vez, si el índice
  no existe todavía, se reconstruye recorriendo el árbol completo una única vez. Límite
  conocido: una exportación escrita directamente por el CLI en la misma carpeta que usa la
  consola no queda indexada hasta que se borre el índice y se reconstruya.
- **Un solo lugar para el chequeo CSRF+origen**: nueva función `_csrf_rejection()` en
  `operator_api.py`, que reemplaza ~25 copias casi idénticas del mismo bloque de validación
  repetidas en rutas POST distintas. Comportamiento idéntico (se verificó que la suite completa
  sigue en verde); solo cambia que ahora hay un único lugar para mantenerlo.
- **Miniatura real en la revisión de imágenes**: la tarjeta de cada candidato de imagen mostraba
  un placeholder de texto "IMG"; ahora muestra la foto real, leída de solo lectura directamente
  del ZIP en cuarentena (verificada por SHA-256/CRC igual que al materializar, pero sin copiar
  ni aprobar nada) y reducida a una miniatura de 320px. Nueva ruta
  `GET /operator/images/candidates/{id}/preview`.
- **Vista previa de cambios campo por campo antes de aplicar el plan**: la inspección del
  dry-run ya mostraba conteos agregados (nuevos/actualizan/sin cambios) pero no qué campo
  cambiaba en cada producto que "actualiza algo existente". Ahora hay un panel plegable que
  reutiliza el `field_diffs` que `build_product_diff` ya calculaba al generar el plan (no se
  recalcula nada nuevo), mostrando solo los campos que realmente cambian, antes/después.
- **Mensajes de error menos técnicos**: cuatro `RuntimeError` internos en el flujo de aplicar un
  plan (`application.py`) usaban jerga interna que un operador no técnico vería tal cual si
  algo salía mal (ej. "El UPDATE controlado no devolvió evidencia de before/after.", "...después
  del insert idempotente."). Se reescribieron para explicar que es un problema interno y sugerir
  contactar soporte, en vez de exponer mecánica de base de datos. Son casos que no deberían
  ocurrir en operación normal (invariantes internos), así que no había nada que un operador
  pudiera "arreglar" con la redacción anterior tampoco.
- Verificación: 365 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
- **No incluido en este bloque, sin pedirlo explícitamente**: commit a git (regla dura: solo se
  hace si se pide de forma explícita).

## Bloque 2026-09-04 (cont. 4): fotos variantes por producto en el HTML autónomo

- Pedido del usuario: en el HTML autónomo, la tarjeta muestra la foto principal; al tocarla se
  abre la ficha y ahí deben verse TODAS las fotos del producto, no solo una. Antes de este
  bloque no existía soporte para más de una foto por producto en ninguna parte del sistema —
  confirmado con una investigación completa del pipeline de imágenes antes de tocar nada.
- **Convención de archivo**: `REF-1234.jpg` sigue siendo la foto principal (sin cambios);
  `REF-1234-2.jpg`, `REF-1234-3.jpg`, etc. son fotos adicionales de la misma referencia — esta
  convención ya estaba anotada como pendiente desde el bloque de "Modo simple" del 2 de
  septiembre y es exactamente lo que se implementó ahora. El sufijo se limita a 1-2 dígitos
  (2 a 99) a propósito: una referencia real que termine en varios dígitos (`REF-1234`) nunca se
  confunde con un índice de variante porque siempre se intenta la coincidencia exacta completa
  primero; el sufijo es solo un respaldo cuando esa coincidencia exacta no encuentra nada.
- **Migración `0026_product_photo_variants.sql`** (aditiva, no toca la tabla de la foto
  principal): agrega `variant_index` opcional a `image_product_candidate` y crea
  `approved_image_variant` — mismo patrón append-only que `approved_image_materialization`,
  pero permite varias filas por producto (una por índice de variante) en vez de una sola. La
  foto principal sigue viviendo exactamente donde vivía; nada de lo ya construido y probado se
  tocó ni se migró.
- **Coincidencia y materialización**: `image_match_review.py` ahora reconoce el sufijo y lo
  guarda en el candidato (algoritmo subido a `exact-approved-reference-v2`, aceptando también
  `v1` para no invalidar candidatos históricos). `materialize_approved_image()` decide sola —
  sin que ningún llamador tenga que saberlo — si el candidato es la foto principal o una
  variante, y publica en la tabla correcta; así "Modo simple" (que aprueba y materializa todo
  en lote automáticamente) funciona sin cambios adicionales en su flujo.
- **Release y exportación**: el snapshot del release ahora incluye `variant_images` (arreglo
  ordenado, aditivo — no se subió `snapshot_schema_version` porque un campo nuevo opcional no
  rompe releases ya publicados). `_package_images` empaqueta también las variantes; el HTML
  digital y el autónomo arman una galería real: la tarjeta muestra la foto principal con un
  aviso "N fotos", y al abrir la ficha aparece una fila de miniaturas para cambiar de foto sin
  cerrar la vista. **Solo el HTML se tocó** — PDF, PPTX, InDesign y las vistas previas de la
  consola del operador siguen mostrando exclusivamente la foto principal, por decisión de
  alcance (así lo pidió el usuario y evita rediseñar formatos de página fija).
- Verificación: 354 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
- Pendiente: aplicar la migración 0026 (junto con las 0021-0025 ya pendientes) contra la base
  real; subir una foto de prueba con sufijo `-2` a través de Modo simple y confirmar visualmente
  la galería en un HTML autónomo generado de verdad.

**Corrección posterior (mismo día):** el usuario corrió `ACTUALIZAR-SISTEMA.cmd` contra la base
real y 0026 falló en la validación final del ledger ("faltan entradas 0017-0026"). Causa real:
el archivo de migración aplicó todo su DDL (tabla, columnas, índices, trigger — eso ya quedó
permanentemente en la base, sin ningún problema) pero se me olvidó el `INSERT INTO
perfect_catalog.schema_migration` final que sí tienen todas las demás migraciones desde la
0017. Se corrigió el archivo para (a) insertar su propia fila de ledger y (b) usar guardas
`IF NOT EXISTS`/`DROP CONSTRAINT IF EXISTS` en cada sentencia, porque al volver a correr el
updater con el esquema ya aplicado pero sin ledger, `apply_pending_migrations.sql` vuelve a
ejecutar el archivo completo (ruta "SCHEMA_AHEAD_OF_LEDGER") y sin esas guardas habría fallado
de nuevo intentando recrear objetos que ya existen. Se agregó `test_records_its_own_ledger_entry`
y `test_every_ddl_statement_can_safely_rerun_after_a_partial_apply` a
`tests/test_product_photo_variants_migration.py` para que este tipo de error no vuelva a pasar
inadvertido. Pendiente: el usuario debe volver a correr `ACTUALIZAR-SISTEMA.cmd`; esta vez debe
completar sin error ya que el esquema ya existe y solo falta escribir la fila del ledger.

## Bloque 2026-09-04 (cont. 3): explorar por categoría, rendimiento de releases y registro vehicular ampliado

- **Nueva pestaña "Explorar por categoría"** en Catálogos (`/operator/catalogs/{release_id}/browse`):
  navegación de solo lectura del release publicado completo (no una muestra), en pestañas reales
  por categoría o por marca vehicular (con conteo por pestaña), paginada dentro de cada una.
  Reutiliza el mismo motor de miniaturas ya existente en la vista previa de composición. Nueva
  función `browse_catalog_release` (`catalog_export_job.py`), gateway y ruta siguiendo el mismo
  patrón que la vista previa InDesign existente.
- **Caché en memoria del release publicado** (`publication.py::load_published_release`): el
  contenido verificado (items + hashes) se cachea por `release_id` porque un release publicado
  nunca cambia de contenido una vez construido — recalcular el hash de miles de productos en
  cada exportación/vista previa/pestaña era trabajo repetido e inútil a partir de la segunda
  llamada. El **estado** (publicado/archivado) sí se revuelve a consultar en cada llamada aunque
  el contenido esté en caché, para seguir rechazando un release archivado igual que antes —
  probado explícitamente con un test que archiva un release entre dos llamadas.
- **Segunda caché** (`catalog_export_job.py::_cached_export_rows`) para el resultado ya
  revalidado de `export_rows_from_release`, usada por `browse_catalog_release` y por el
  servidor de miniaturas (`resolve_catalog_preview_image`) — sin esta segunda caché, cada
  miniatura individual de la pestaña nueva habría vuelto a revalidar el release completo.
- **Tope de tamaño para el HTML autónomo con fotos incrustadas** (200 MiB de fotos
  seleccionadas): antes no existía ningún límite y a 25,000+ productos con fotos podía intentar
  generar un HTML de varios GB. Ahora se rechaza con un mensaje claro que sugiere el ZIP digital.
- **Registro vehicular ampliado** (`vehicle_makes.py`): se agregó `V.W`/`V.W.` como alias de
  Volkswagen (reportado por el usuario), más camiones pesados (Fuso, UD Trucks, Western Star,
  Shacman, Sinotruk, Higer, Yutong), autos nuevos (MG, Leapmotor, Denza) y motocicletas (Yamaha,
  Kawasaki, KTM, Royal Enfield, Harley-Davidson, Ducati, Vespa, Piaggio, Aprilia, Italika, AKT,
  Bajaj, TVS, Eicher, Zongshen, Loncin, Benelli, Force Motors, Hero MotoCorp) — 129 marcas / 155
  alias en total. `Force Motors`/`Hero MotoCorp` solo aceptan el nombre completo, no la palabra
  suelta ("force"/"hero"), siguiendo la misma regla de no-ambigüedad que ya excluye RAM/SEAT/MAN.
- **Limpieza de código identificada y aprobada por el usuario:**
  - Eliminada `assert_apply_allowed` (`importer.py`): función muerta que siempre lanzaba
    `NotImplementedError`; el guard real es `assert_applicable_items` (`application.py`).
  - `_optimized_raster` ahora acepta una caché opcional por llamada de exportación: si la misma
    foto se usa en varios productos del mismo PDF/PPTX/HTML, ya no se re-decodifica ni
    re-comprime una vez por producto.
  - Unificada en `group_values()` (`catalog_exports.py`) la lógica de "expandir en abanico
    cuando se agrupa por marca vehicular", que antes estaba copiada de forma independiente en
    `_groups`, `_indesign_rows` y `build_catalog_preview` (y en la nueva `browse_catalog_release`).
  - **Bug real encontrado de paso:** `list_operator_catalog_exports` ordenaba el historial de
    exportaciones por el texto del UUID de carpeta (aleatorio), no por fecha real — "más
    reciente primero" no reflejaba la realidad. Se corrigió para ordenar por la fecha real de
    modificación del manifiesto. **Pendiente, no resuelto todavía:** el listado sigue teniendo
    que recorrer todo el árbol histórico de exportaciones en cada consulta — evitar eso de
    verdad requiere un índice liviano o una política de retención/limpieza (borra archivos, no
    registros de auditoría), ninguna de las dos implementada aún porque implica borrar datos o
    agregar infraestructura nueva; requiere decisión explícita antes de tocarlo.
- Verificación: 340 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.

## Bloque 2026-09-04 (cont. 2): generaliza los hardcodes de NATSUKI y retira el modo Excel directo

- El usuario notó que buena parte del código seguía asumiendo NATSUKI como "la" marca por defecto
  aunque el sistema ya es multiempresa/multimarca. Auditoría con 2 agentes Explore + lectura
  directa confirmó los puntos concretos; el usuario decidió (vía preguntas dirigidas) arreglar el
  visor en vivo para cualquier marca en vez de retirarlo, eliminar del todo el modo Excel-directo,
  usar gris neutro como color por defecto de una marca nueva, y dejar el menú amplio de mejoras
  posibles solo como referencia sin implementar.
- **PDF genérico:** `generate_catalog_pdf` (`catalog_exports.py`) ya no aplica Barlow
  Condensed/DM Sans de Natsuki a cualquier marca. Nueva `_catalog_pdf_fonts()` usa las fuentes
  reales de Natsuki solo si el logo activo es el suyo (mismo gate que `_logo_path`); cualquier otra
  marca recibe Helvetica estándar de ReportLab, ya que no hay `.ttf` bundleados para KMC/PDM/etc.
  Los PDF de Natsuki no cambian visualmente.
- **Visor en vivo generalizado:** `ReleaseCatalogRepository` (`web.py`) ya no tiene `"NATSUKI"`
  como marca por defecto — `brand` pasa a ser obligatorio, y el repositorio expone
  `brand_name`/`brand_code` reales leídos del release. La plantilla del visor y la ficha de
  producto imprimible ya no dicen "Perfect Trading / Natsuki" ni "Producto Natsuki" fijo; usan el
  nombre real de la marca servida. `INICIAR-CATALOGO-PUBLICADO.cmd` ya no abre siempre NATSUKI:
  ahora delega en `db/bootstrap/start_published_catalog.ps1`, que primero lista qué marcas tienen
  un release publicado y pregunta cuál abrir (mismo patrón de contraseña oculta que no se guarda).
- **Modo Excel-directo retirado por completo** (mismo riesgo que `INICIAR-SERVER.cmd`, ya borrado
  antes: evadía cuarentena, dry-run y aprobación). Se eliminaron `CatalogRepository`,
  `ExcelCatalogRepository`, `AutoExcelCatalogRepository` y sus helpers de `web.py` (cero llamadores
  reales), los flags `--source`/`--source-dir` de `api.py`, y `scripts/run_catalog_web.py` entero.
  `--brand` es ahora el único camino y es obligatorio.
- **Colores neutros por defecto:** el formulario "Añadir una marca" ya no precarga los colores
  exactos de Natsuki (`#C60012`/`#202327`/`#16191D`); ahora arranca en gris neutro
  (`#1F2937`/`#374151`/`#111827`) que no coincide con ninguna marca real. El operador sigue
  eligiendo el color real antes de guardar.
- **Otros hardcodes de bajo riesgo corregidos de paso:** `CONTRACT_VERSION` renombrado de
  `"natsuki-empaques-v0.2"` a `"perfect-catalog-v0.2"` (valor opaco comparado por igualdad, sin
  cambio de comportamiento); placeholder de versión en Catálogos cambiado de `"2026.08-natsuki"` a
  `"2026.08"`; el parámetro `brand_code`/`brand_name` con default `"NATSUKI"` se quitó de
  `promote_intake_to_dry_run`, `_promote_intake_to_dry_run_locked`, el protocolo `promote_intake`
  y `build_release`/`_build_release_in_connection` — todo caller real ya lo pasaba explícito.
- **Bug real encontrado de paso:** al quitar el default de `_build_release_in_connection`, se vio
  que el parámetro `brand_name` (ya requerido en el formulario "Construir versión" de Catálogos,
  pensado como confirmación tipo "escribe la marca exacta del plan") nunca se validaba contra nada
  — se aceptaba y se descartaba en silencio. Se agregó la comprobación real: si la marca escrita no
  coincide con la marca resuelta del plan aplicado, se rechaza con `PermissionError`, igual que las
  demás confirmaciones "expected_*" del proyecto.
- Verificación: 325 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
- Pendiente: correr `ACTUALIZAR-SISTEMA.cmd` contra la base real (sigue pendiente desde el bloque
  de NATSUKI-Company de abajo); generar un PDF de una marca sin fuentes propias para confirmar
  visualmente Helvetica; abrir el visor en vivo para una marca distinta de NATSUKI una vez tenga
  release publicado. El menú amplio de mejoras (calidad de exportación, revisión de imágenes, cola
  de revisión, cobertura de pruebas, rendimiento a escala, etc.) se mostró al usuario como
  referencia y queda sin implementar hasta que lo pida explícitamente.

## Bloque 2026-09-04 (cont.): NATSUKI vuelve a ser Company propia (revierte parte de 0021)

- Decisión explícita del usuario, confirmada dos veces: NATSUKI vuelve a ser una **Company
  independiente**, no una marca de Perfect. MASAKI y EXACTCARS quedan exactamente como estaban
  (marcas de Perfect) — el usuario lo confirmó por separado.
- Auditoría real vía `AUDITAR-EMPRESAS-MARCAS.cmd` (nueva herramienta de solo lectura, mismo
  patrón que `PREPARAR-MULTIEMPRESA.cmd`) antes de escribir nada: confirmó que el Company legacy
  de NATSUKI (`ee7c7e0c-398f-5e35-9d79-c97d761f8672`) seguía existiendo, solo desactivado por 0021
  ("Company legacy conservada por referencias historicas"), con 896 productos activos bajo su
  Brand. A1 ya estaba correctamente bajo KMC — no hacía falta tocarlo.
- Migración forward-only `0025_natsuki_company_restored.sql`: **reactiva** el Company legacy (no
  crea uno nuevo, conserva su UUID e historial), mueve `brand.company_id` y
  `brand_profile.company_id` de NATSUKI de vuelta a esa Company, y resincroniza
  `import_plan.company_id` de sus planes — mismo mecanismo que usó 0021 en la dirección opuesta.
  No toca MASAKI ni EXACTCARS.
- `is_company_brand_allowed()` (`import_context.py`) actualizado: NATSUKI ahora es Company válida
  (solo admite su propia Brand NATSUKI, igual que KMC solo admite A1); ya no está bloqueada como
  antes. La copia de "Añadir empresa" en la consola se corrigió para no decir que Natsuki debe
  crearse como marca.
- Verificación: 321 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
  Pendiente: aplicar 0025 vía `ACTUALIZAR-SISTEMA.cmd` contra la base real y confirmar que NATSUKI
  vuelve a aparecer como Company seleccionable con sus 896 productos intactos.

## Bloque 2026-09-04 (cont.): acento de color por Company activa en la consola web

- La consola del operador (nav, botones, marca) era siempre verde fijo sin importar qué Company
  estuviera activa — solo el catálogo exportado reflejaba colores de marca/empresa. Ahora, si la
  Company activa tiene una identidad corporativa cargada (Marcas → Identidad corporativa), la
  consola adopta su color principal/secundario como acento (`--forest`, `--forest-dark` calculado,
  `--lime`). Ink/fondo/tarjetas se mantienen neutros a propósito para no arriesgar legibilidad.
- Implementado como hoja de estilos externa (`GET /operator/theme.css`, mismo origen) en vez de
  `<style>` inline, para no debilitar `style-src 'self'` del CSP existente. Los colores se calculan
  una vez al iniciar sesión o cambiar de Company (mismo patrón de cache que `company_name`); si se
  edita la identidad corporativa mientras la sesión sigue abierta, hace falta volver a seleccionar
  la Company para verla reflejada — limitación conocida, igual a la de `company_name`.
- Sin identidad corporativa cargada, la hoja responde vacía y la consola se ve igual que siempre
  (verde por defecto). No se validó contraste WCAG del color secundario de Company contra el fondo
  del anillo de foco (`--lime` se usa para `focus-visible`); si una empresa carga un secundario muy
  claro podría verse poco legible ahí — mismo tipo de riesgo que ya existe para marcas de producto.
- Verificación: 315 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.

## Bloque 2026-09-04: fix de exportación, atajo HTML rápido y copiar referencia

- Corregido bug real en producción: `create_operator_catalog_export` fallaba con
  `[WinError 5] Acceso denegado` al mover el directorio temporal de exportación a su destino
  final — típico choque con el antivirus escaneando archivos recién escritos en Windows. Se agregó
  `_replace_with_retry` (hasta 5 intentos con espera creciente) alrededor del único `replace()`
  involucrado; si el bloqueo persiste tras agotar los intentos, el error real se sigue mostrando.
- **Botón "HTML autónomo ya"** en cada release publicado: genera solo el HTML autónomo con
  valores por defecto (categoría, 2 columnas, todo visible) en un solo clic, sin pasar por el
  formulario completo de exportación. PDF/PPTX/InDesign quedan en "Configurar exportación" como
  antes. Reutiliza `gateway.export_catalog` sin tocar su lógica.
- La inspección del dry-run (`/operator/import-plans/{id}`) ahora desglosa **nuevos / actualizan
  algo existente / sin cambios** en vez de solo un total de operaciones — la clasificación ya
  existía desde el bloque del 2 de septiembre, pero no se mostraba. Si un Excel repetido no agrega
  ni actualiza nada, aparece un aviso explícito.
- El HTML autónomo (y el ligero) suman un **botón de copiar referencia** por ficha: copia al
  portapapeles con `navigator.clipboard`, con reserva a `execCommand('copy')` vía textarea oculto
  para navegadores/contextos donde el API async no esté disponible (sigue funcionando 100% offline
  desde `file://`). Sin integración de WhatsApp — decisión explícita del usuario.
- Verificación: 312 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales.
  Pendiente: confirmar en un release real que el botón rápido y el desglose se ven bien en
  navegador, y que el reintento realmente resuelve el WinError 5 la próxima vez que ocurra.

### Pendiente de la conversación sobre "catálogos rápidos"

El usuario quiere priorizar temporalmente el HTML autónomo sobre PDF/PPTX/InDesign y seguir
simplificando la interfaz. Ideas ya evaluadas y no elegidas todavía (no descartadas, solo no
priorizadas): recordar la última configuración de exportación por marca, atajo directo
"Actualizar catálogo de [Marca]" desde Catálogos, vista de impresión dedicada del HTML, orden
por nombre/referencia además de filtrar. Retomar si el usuario pide más mejoras en esta línea.

## Bloque 2026-09-02 (cont.): modo simple, sugerencia de color por logo y archivado de releases

- Nueva pantalla **Modo simple** (`/operator/simple`): un solo formulario (Excel + carpeta de fotos
  vía selector de carpeta del navegador + marca + motivo) encadena, con una sola confirmación,
  ingreso a cuarentena de ambos archivos, dry-run, preparación (aprobación+aplicación) del plan e
  indexado/vinculación automática de fotos cuyo nombre de archivo coincide exactamente con una
  referencia ya aprobada. No publica nada: identidades nuevas y publicación de release siguen
  siendo pasos humanos separados. Reutiliza integralmente el motor existente (intake, dry-run,
  `apply_controlled_product_update` vía 0022, `exact-approved-reference-v1`); no se tocó SQL.
- El emparejamiento exacto sigue siendo por nombre de archivo completo (`REF-1234.jpg` ==
  referencia `REF-1234`); no existe todavía soporte para variantes con sufijo (`REF-1234-2.jpg`)
  como segunda foto del mismo producto — quedaría pendiente si se necesita más adelante.
- La pantalla **Marcas** ahora ofrece extraer 2 colores dominantes de un logo directamente en el
  navegador (canvas, sin subir el archivo) al crear un perfil, con confirmación explícita antes de
  aplicarlos a los selectores de color.
- Nueva acción **Archivar versión** en Catálogos: expone `archive_release` (existía en
  `publication.py`/CLI pero no en la consola web) para releases publicados. No borra nada; solo
  cambia `status` a `archived` de forma auditada y reversible en su historial. Responde el pedido
  de "no hay opción para eliminar" sin romper el principio append-only del proyecto.
- Se retiró `INICIAR-SERVER.cmd` (visor XLSX del piloto, evadía cuarentena/dry-run/aprobación).
- Modo simple admite además una carpeta local del servidor como alternativa a subir por el
  navegador (`local_images_path`, sin confinar a una raíz fija — decisión explícita del usuario
  frente a la alternativa más segura de restringir a una carpeta base; el proceso lee cualquier
  ruta de Windows a la que tenga acceso). Solo filtra por extensión de imagen admitida; el resto
  de la carpeta (Thumbs.db, sidecars) se ignora en silencio.
- Archivado auditado de ingresos viejos (migración `0024_intake_submission_archiving.sql`):
  `intake_submission` (0007) es completamente append-only y eso no se tocó. El estado "archivado"
  se registra en una tabla de eventos separada (`intake_submission_archive_event`, mismo patrón que
  `image_product_decision`); el último evento por ingreso determina si está activo o archivado.
  Nueva pantalla en Ingresos: filtro Activos/Archivados/Todos y botón archivar/restaurar por fila,
  ambos reversibles y sin borrar bytes ni evidencia SHA-256.
- Verificación: 308 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales. Ningún
  paso de este bloque corrió contra un Postgres real; falta esa verificación antes de producción.

### Decisiones del usuario en este bloque

- Limpieza de ingresos/Excels viejos: **archivar/ocultar, nunca borrar bytes** — implementado
  arriba (0024), mismo patrón que Company/Brand/release.
- Marca de agua de destinatario/fecha en el HTML autónomo: **no por ahora**.
- Carpeta local de imágenes: **ruta libre de Windows sin confinamiento** (ver arriba) — el usuario
  priorizó flexibilidad sobre el patrón de confinamiento que ya usa `intake_root` en el resto del
  sistema; quedó documentado como decisión consciente, no como omisión.

### Pendiente explícito para la próxima sesión

1. Ejecutar `ACTUALIZAR-SISTEMA.cmd` (aplica 0021-0024) y probar en vivo: vincular Brand↔Perfil,
   modo simple completo (subida por navegador y por carpeta local), archivar un release real, y
   archivar/restaurar un ingreso real.
2. Ningún pedido explícito de Isa quedó sin atender al cierre de este bloque.

## Bloque 2026-09-02: auditoría del bloque multiempresa y vínculo Brand-Perfil (0023)

- Auditoría del bloque "importador multiempresa" (trabajado en Codex, continuado en Claude Code):
  el `scope.filters` que graba `import_batch` usaba las constantes fijas `BRAND`/`"empaque"` en vez
  del `brand_code`/`family` reales del dry-run, dejando auditoría incorrecta para cualquier Company
  distinta de NATSUKI. Corregido en `importer.py`.
- Hallazgo crítico: ninguna migración ni pantalla vincula `brand.brand_profile_id` para Companies
  nuevas (KMC/A1, PDM); solo NATSUKI quedó vinculada por un `UPDATE` puntual en `0014`. El paso que
  antes resolvía esto en `approve_and_apply_plan` (buscar el perfil por código en el momento de
  aprobar) fue retirado en el mismo bloque de Codex sin reemplazo, dejando cualquier dry-run de una
  Company nueva con un plan que nunca puede aprobarse.
- Migración forward-only `0023_brand_profile_linking.sql` agrega vínculo auditado y explícito
  Brand → Brand Profile (`brand_profile_link_event`, append-only, con control de concurrencia
  optimista sobre el vínculo previo). Nueva pantalla en **Marcas**: lista las Brands de la Company
  activa y su estado de vínculo, con formulario de vincular/re-vincular con motivo y confirmación.
  `perfect_catalog_app` gana `UPDATE (brand_profile_id, updated_at)` sobre `brand`, antes sin permiso
  alguno de escritura ahí salvo INSERT.
- Se retiró `INICIAR-SERVER.cmd`: abría `perfect-catalog-api` en modo `--source-dir`, leyendo Excel
  directamente sin cuarentena, dry-run ni aprobación — una vía lateral que evadía todo el pipeline
  de auditoría. `INICIAR-CATALOGO-PUBLICADO.cmd` y el HTML autónomo cubren los casos de uso reales.
- Verificado en código (no requiere cambios): los colores del HTML autónomo ya derivan del perfil de
  marca del producto (`_theme()` en `catalog_exports.py`), no de un tema fijo; la Company solo firma
  el pie. Vigente desde v1.23/v1.39.
- Verificación: 295 pruebas correctas, 6 integraciones PostgreSQL omitidas sin credenciales. El
  vínculo Brand-Perfil en vivo (0023 aplicada, formulario end-to-end) sigue sin probarse contra un
  Postgres real, igual que el resto del bloque 0021-0022.

## Bloque 2026-09-01: importador multiempresa, fase inicial

- El dry-run valida Company activa y Brand activa perteneciente a ella antes de resolver referencias.
- La resolución usa `source_system_id + brand_id + referencia interna normalizada`.
- Se añadieron los estados efectivos `CREATE`, `NO_CHANGE` y `UPDATE`, con `field_diffs` y
  `KEEP_EXISTING` para entradas vacías; NATSUKI/empaques queda como perfil piloto compatible.
- `NO_CHANGE` no escribe datos empresariales. `UPDATE` se clasifica, pero el apply lo bloquea antes
  de escribir porque el trigger actual de `product_template` protege los datos de catálogo.
- No se tocaron migraciones en esta fase ni se alteró PostgreSQL. Resolver el bloqueo de UPDATE
  requiere una decisión posterior de esquema, no una edición de 0017-0021.
- Tests focalizados: 89 correctos. Falta ejecutar la suite completa y decidir la migración posterior
  necesaria para UPDATE antes de habilitarlo.

## Bloque 2026-08-31: filtros móviles y estado offline del HTML

- El HTML ligero y el autónomo incorporan filtros combinables por categoría, marca de producto y
  marca vehicular. Las opciones se derivan únicamente del snapshot congelado y no consultan red.
- El usuario puede alternar entre Tarjetas y Lista. En móvil, la lista compacta imagen y referencia
  sin recortar la fotografía; el visor completo y `object-fit: contain` permanecen intactos.
- Búsqueda, filtros, vista y posición de scroll se conservan en `localStorage` bajo una clave ligada
  al checksum/version del release. Si el navegador bloquea almacenamiento, el catálogo continúa
  funcionando sin persistencia.
- Validación real en Edge con viewport 390x844: filtros combinados, ocultación de secciones, vista
  Lista y restauración tras recarga correctos. El archivo sigue siendo autocontenido y offline.
- No requiere migración. Hay que generar un HTML nuevo para incorporar estos controles.
- Verificación automatizada: compilación sin advertencias, `git diff --check` limpio y 277 pruebas
  correctas; 6 integraciones PostgreSQL omitidas sin credenciales.

## Bloque 2026-08-31: jerarquía cromática empresa/marca (v1.39)

- La marca de producto sigue controlando fondo, texto, color principal/secundario, tipografía,
  portada y marca de agua. La empresa no sustituye esa dirección visual.
- Los colores corporativos congelados ahora firman discretamente el pie del HTML autónomo, las
  páginas interiores del PDF, las diapositivas y las páginas de InDesign. El nombre empresarial se
  conserva junto a la firma; el logo corporativo continúa en portada.
- Catálogos muestra en cada release la marca activa y sus dos muestras de color, evitando confundir
  ediciones de Natsuki, Exact Cars u otra marca de la Company seleccionada.
- Los logos vehiculares permanecen exclusivamente contextuales junto a su marca vehicular.
- No requiere migración. Hay que generar entregables nuevos para incorporar los detalles visuales.
- Verificación: firma PDF separada de checksum/número de página, compilación correcta,
  `git diff --check` limpio y 277 pruebas correctas; 6 omitidas.

## Bloque 2026-08-31: referencias A1 dentro de la revisión y publicación (v1.38)

- Al aplicar un plan nuevo, los candidatos OEM, FMSI, adicionales y alternos se materializan como
  `product_reference` pendientes. Una defensa adicional impide asignar un código no rechazado a
  otra identidad de la misma marca aunque el estado haya cambiado después del dry-run.
- La ficha de revisión muestra todas las A1 detectadas y el `review_sha256` las compromete. Aprobar
  o rechazar una identidad decide en la misma transacción su referencia interna, todas sus A1 y sus
  aplicaciones vehiculares; un estado parcial se trata como inconsistente.
- Los releases sólo incorporan A1 aprobadas y se bloquean si queda alguna pendiente. El snapshot y
  el HTML exponen OEM, FMSI, adicionales/alternas sin inventar información.
- No requiere migración: reutiliza `product_reference`. Los planes antiguos no ganan candidatos
  retroactivamente; hay que generar y aplicar un dry-run nuevo para aprovechar esta fase.
- Verificación: compilación correcta, `git diff --check` limpio y 277 pruebas correctas; 6 omitidas.

## Bloque 2026-08-31: candidatos A1 seguros en dry-run (reglas v0.4)

- El enriquecimiento convierte OEM, FMSI, referencias adicionales dedicadas y referencias alternas
  del nombre en candidatos tipados con original, normalizada, confianza, procedencia y estado
  `pending`. Duplicados se consolidan y nunca se replica la referencia interna como A1.
- El dry-run detecta el mismo código candidato en productos distintos del archivo y consulta los
  propietarios no rechazados dentro de la Company activa. Cualquier colisión crea
  `cross_reference_conflict` de severidad error y bloquea esa identidad sin escribir datos maestros.
- Nuevos planes usan `normalization-v0.4`; los planes exactos v0.3 siguen verificables para no dejar
  trabajo ya revisado inutilizable. Versiones anteriores permanecen rechazadas.
- Esta fase conserva candidatos únicamente en staging/plan y los incluye en el fingerprint. No los
  inserta todavía en `product_reference` ni los publica. Siguiente compuerta: mostrarlos en la cola
  de identidad y materializarlos pendientes para que la misma decisión humana los apruebe o rechace.

## Bloque 2026-08-31: búsqueda multipalabra offline en HTML

- El HTML ligero y el autónomo generan un índice explícito por producto con referencia original y
  normalizada, nombre, pieza/categoría, marca de producto/vehículo, aplicaciones, motores, OEM,
  FMSI y referencias adicionales. Los campos siguen siendo buscables aunque la edición los oculte.
- Las consultas se pliegan sin acentos, aceptan palabras en cualquier orden y comparan también una
  versión alfanumérica compacta: `NK001` encuentra `NK-001` y `hilux empaque 1kd` exige los tres
  términos dentro de la misma ficha. Todo funciona localmente, sin `fetch` ni servidor.
- Verificación focalizada: 28 pruebas de exportación correctas. No requiere migración PostgreSQL;
  hay que generar una exportación HTML nueva para incorporar el buscador.

## Bloque 2026-08-31: ingresos e imágenes aislados por Company (v1.37)

- `ACTUALIZAR-SISTEMA.cmd` conserva ahora la salida del último intento en
  `logs/actualizar-sistema-ultimo.log`; no registra la contraseña. Se añadió después de que un fallo
  local `psql: 3` quedara fuera de la captura y sin diagnóstico persistente.
- La migración `0020_company_intake_context.sql` persiste `company_id` en cada ingreso y plan nuevo.
  Los planes históricos se rellenan mediante su perfil de marca; los ingresos históricos permanecen
  sin asignar y ocultos porque son append-only y no deben reescribirse durante una migración.
- Los triggers de base rechazan nuevos ingresos o planes sin Company incluso si se omite la API. El
  actualizador único calcula y valida el checksum 0020 y comprueba el ledger 0017–0020.
- La Company activa acompaña el flujo completo: recepción, promoción Odoo, dry-run, selección de
  marca, candidatos de imagen, decisiones individuales/en lote y materialización de copias.
- Las consultas y las rutas con UUID de ingreso, índice o candidato verifican pertenencia antes de
  mostrar o modificar recursos. Las referencias existentes usadas por el parser también se limitan
  a Brands de la empresa activa.
- Consola actualizada a v1.37.0. Verificación: compilación correcta, scripts PowerShell válidos,
  `git diff --check` limpio y 273 pruebas correctas; 6 omitidas.
- Acción local pendiente: ejecutar `ACTUALIZAR-SISTEMA.cmd` una vez antes de volver a iniciar el
  revisor. No ejecutar migraciones numeradas manualmente.

## Bloque 2026-08-31: Company activa e identidad corporativa 0019

- La consola v1.36 incorpora selector de Company después del login. Con una sola Company activa la
  selección es automática; con varias exige POST de mismo origen y CSRF. La Company elegida queda
  ligada a la sesión firmada y aparece en el encabezado.
- Planes aplicados, releases, perfiles de marca e identidad corporativa se consultan por
  `company_id`. Los ingresos siguen compartidos deliberadamente hasta persistir su Company en el
  siguiente bloque; la interfaz lo indica y no promete un aislamiento inexistente.
- Un guard de servidor comprueba los UUID directos de planes, releases, exportaciones y logos antes
  de ejecutar cada ruta; un recurso perteneciente a otra Company responde como no encontrado.
- 0019 añade Company obligatoria a `brand_profile`, liga cada identidad scope `company` a una
  Company exacta y migra las revisiones corporativas históricas a PERFECT. Las identidades Brand y
  vehicle_make conservan un único destino mediante CHECK.
- La creación/materialización de una marca hereda Company desde su perfil; corrige además el INSERT
  que habría fallado después de que 0018 hiciera `brand.company_id` obligatorio.
- `ACTUALIZAR-SISTEMA.cmd` y `LIMPIAR-IMPORTACIONES.cmd` incorporan checksum y validación de 0019.
- Verificación: 272 pruebas correctas; 6 integraciones PostgreSQL omitidas sin credenciales.

## Bloque 2026-08-31: validación automática posterior a Company

- `ACTUALIZAR-SISTEMA.cmd` no se limita a detectar/aplicar 0017-0018: ahora falla de forma visible
  si el ledger no contiene ambas entradas, faltan Companies iniciales, existe una Brand sin Company
  o EXACTCARS/NATSUKI quedaron asignadas a una empresa incorrecta.
- Al completar muestra un resumen Company -> cantidad de Brands y confirma explícitamente que la
  base quedó actualizada **y validada**. Reejecutar el actualizador es seguro e idempotente.

## Bloque 2026-08-31: limpieza de ejecutores de migración obsoletos

- Se eliminaron 26 wrappers internos duplicados (`apply_*_migration.sql` y
  `run_*_migration.ps1`). Eran rutas históricas de ejecución individual, ya sustituidas por
  `ACTUALIZAR-SISTEMA.cmd` y el actualizador central con detección de pendientes.
- Se conservaron todos los accesos públicos con funciones vigentes: iniciar operador, iniciar
  catálogo publicado, actualizar sistema, preparar multiempresa, limpiar importaciones,
  restablecer acceso y validar bloque.
- La reconstrucción voluntaria de `LIMPIAR-IMPORTACIONES.cmd` aplica ahora directamente 0001-0018
  en orden y entrega los checksums de 0017-0018. Así no depende de archivos retirados ni falla al
  reconstruir el ledger multiempresa.
- Los tests de contrato verifican la ruta central y no ejecutores individuales obsoletos.
- Verificación: 266 pruebas correctas; 6 integraciones PostgreSQL omitidas sin credenciales. No se
  borraron importaciones, imágenes, respaldos ni recursos de marca durante esta limpieza de código.

## Bloque 2026-08-31: inventario de marcas desde recurso de red

- Lectura sin modificaciones de `PERFECT/HIGH RES` y `PDM/HIGH RES`: 29 y 89 carpetas.
- Se documentaron listas exactas, dos colisiones (`ASIA INC`, `KDT`), agrupadores probables y tres
  conflictos de jerarquía (`KMC`, `MASAKI`, `NATSUKI` bajo el árbol físico de Perfect).
- La carpeta de imágenes se trata como evidencia secundaria, nunca como fuente maestra. No se
  crearon Brands, no se copiaron imágenes y no se amplió el backfill 0018.
- EXACT CARS permanece confirmada en Perfect Company. Los demás candidatos se conciliarán con
  Odoo antes de nuevas migraciones o importaciones.

## Bloque 2026-08-31: migraciones Company 0017-0018 preparadas

- El usuario confirmó `EXACTCARS -> Perfect Company`; `NATSUKI -> Natsuki Company` ya estaba
  respaldado por la especificación. El mapping real cubre las dos marcas y los 472 productos.
- 0017 crea `schema_migration`, registra checksum SHA-256, actor, versión PostgreSQL y execution ID.
  El actualizador calcula hashes en tiempo de ejecución y se detiene si una migración aplicada cambia.
- 0018 crea Perfect Company, KMC, Natsuki, Masaki y PDM con UUID deterministas; añade
  `brand.company_id`, hace backfill explícito, aborta ante cualquier marca desconocida y sólo entonces
  impone NOT NULL, FK RESTRICT e índice de aislamiento.
- No se agrega Company redundante a productos/categorías: en esta etapa deriva autoritativamente de
  Brand. Se conserva `brand.code` único global y la taxonomía compartida.
- Migraciones preparadas pero aún no aplicadas. Siguiente paso: ejecutar `ACTUALIZAR-SISTEMA.cmd`,
  validar ledger/Companies/mapping y sólo después preparar identidad/contexto 0019.
- Verificación: sintaxis PowerShell y 266 pruebas pasan; 6 integraciones se omiten sin credenciales.

## Bloque 2026-08-31: evidencia real y diseño multiempresa

- Fase 0 ejecutada correctamente: dump custom de 2.214.158 bytes, 427 entradas verificables y
  checksum SHA-256 registrado. PostgreSQL 18.6 confirma las estructuras 0001-0016.
- Base real: 472 productos activos (NATSUKI 193, EXACTCARS 279), dos releases publicados, dos
  perfiles/revisiones visuales `brand`, ninguna identidad `company`, y 472 referencias internas
  aprobadas sin duplicados entre productos.
- `DISENO-MIGRACION-MULTIEMPRESA.md` define Company sin Corporation inicial, Company autoritativa
  por Brand, categorías compartidas, código de Brand global durante transición y etapas 0017A-C/0018.
- NATSUKI queda mapeada con evidencia. El backfill está bloqueado únicamente hasta confirmar a qué
  Company pertenece EXACTCARS; Perfect, A1 y Masaki todavía no existen en la BD.
- El preparador ahora genera automáticamente el archivo SHA-256 para futuros backups.
- Verificación: 263 pruebas pasan; 6 integraciones PostgreSQL siguen omitidas en la suite ordinaria.

## Bloque 2026-08-31: inicio controlado de Fase 0 multiempresa

- `PREPARAR-MULTIEMPRESA.cmd` concentra el primer paso seguro: contraseña `postgres` oculta,
  `pg_dump` completo, verificación mediante `pg_restore --list` y auditoría SQL de sólo lectura.
- Los resultados se guardan fuera de Git en `backups/phase0-multicompany/`. No se ejecutan DDL,
  migraciones ni cambios de datos durante esta fase.
- `audit_pre_multicompany.sql` recopila estructura 0001-0016, cardinalidades, marcas/perfiles,
  productos y releases por marca, identidades, referencias duplicadas y privilegios.
- `MAPPING-COMPANY-BRAND-INICIAL.md` deja explícitas las asignaciones aún pendientes; no permite
  backfill automático ni marcas desconocidas.
- PostgreSQL 18 responde en localhost, pero la inspección autenticada queda pendiente de que el
  usuario ejecute el iniciador localmente. Verificación de código: 263 pruebas pasan, 6 integraciones
  PostgreSQL se omiten sin credenciales.

## Bloque 2026-08-27: contenido editorial automático v1.35

- Las fichas omiten OEM, aplicaciones, motor, categoría o marca cuando el dato no existe, evitando
  llenar el catálogo con textos como `No indicadas`. Referencia y nombre siguen siendo obligatorios.
- El nombre del producto obtiene jerarquía automática en 14 pt, negrita y color primario; la
  referencia conserva 13 pt. Los títulos largos del índice intentan ajustarse dentro de su fila.
- El aviso final informa además la cantidad de fuentes no disponibles y las páginas generadas.
- No requiere migración; hay que generar un paquete InDesign nuevo para usar el JSX v1.35.0.

## Bloque 2026-08-27: índice y navegación editorial InDesign v1.34

- El importador reserva automáticamente las páginas de índice necesarias después de la portada,
  registra cada separador y escribe su número de página real. Admite más de 15 secciones mediante
  páginas de continuación.
- Las páginas editoriales incorporan numeración consistente. El índice usa la marca y categoría
  como jerarquía legible sin modificar las claves internas ni inventar datos de producto.
- No requiere migración; hay que generar un paquete InDesign nuevo para usar el JSX v1.34.0.

## Bloque 2026-08-27: jerarquía vertical de separadores v1.33

- En agrupaciones dobles, la marca vehicular se presenta como título principal y la categoría se
  coloca debajo en una línea independiente. La clave interna conserva ambos valores para no mezclar
  secciones ni alterar el orden del catálogo.
- No requiere migración; hay que generar un paquete InDesign nuevo para incorporar el JSX v1.33.0.

## Bloque 2026-08-27: logos vehiculares con agrupación secundaria v1.32

- El separador ahora conserva por separado la marca vehicular primaria y el título editorial
  combinado. De este modo `Chevrolet · RODAMIENTOS` busca el logo de `Chevrolet` y lo muestra aunque
  el catálogo también esté agrupado por categoría, pieza u otro segundo nivel.
- No requiere migración. Los paquetes InDesign deben regenerarse para incluir el JSX v1.32.0.

## Bloque 2026-08-27: importador InDesign v1.31 y separadores robustos

- Corregido el mojibake heredado en snapshots (`Â·`, vocales acentuadas, `ñ` y `ü`) antes de
  componer títulos, aplicaciones y demás datos editoriales.
- Los separadores amplían el área del título, usan interlineado compacto y ajustan el tamaño entre
  30 y 18 pt únicamente si el texto todavía desborda. El texto de las fichas conserva el mínimo de
  12 pt y su interlineado 1.8.
- El documento guarda la etiqueta `perfect_catalog_importer_version=1.31.0` y el aviso final muestra
  `Perfect Catalog Importer v1.31.0`. Esto permite detectar inmediatamente si se ejecutó una copia
  antigua del JSX.
- Diagnóstico de la prueba manual: el paquete
  `catalogo-2026.27.08-cf8b9ffe.indesign` contiene un `ImportPerfectCatalog.jsx` anterior (16 KB),
  distinto al vigente del proyecto (19 KB), y su JSON sí contiene valores heredados como `Â·`.
  Hay que generar de nuevo el paquete InDesign o sustituir su JSX por el actual antes de probar.

## Bloque 2026-08-27: composición adaptativa InDesign v1.30

- Se diagnosticó el snapshot real de 337 productos: perfil T4, 256 imágenes presentes, 81 ausentes,
  aplicaciones con promedio de 97.7 caracteres y máximo de 335; 174 superan 80 caracteres. El T4
  fijo no podía contener esos datos a 12 pt e interlineado 1.8.
- El importador mantiene T4 para fichas breves y promueve automáticamente contenido extenso a T2 o
  T1 según su carga editorial. En la muestra real resultan 69 T4, 209 T2 y 59 T1. La alerta informa
  cuántas fichas se ampliaron y el preflight continúa reportando cualquier overflow real restante.
- Cuando falta imagen, la ficha recupera todo el espacio reservado para fotografía en lugar de dejar
  un bloque vacío. Las 81 imágenes siguen siendo ausencias reales del release y deben resolverse en
  la revisión web si se desea un catálogo completamente ilustrado.
- Todo texto literal del JSX quedó en ASCII con escapes Unicode, evitando `CatÃ¡logo`/`ImÃ¡genes`
  cuando ExtendScript interpreta el archivo con una página de códigos heredada. No requiere migración.
- El verificador de preflight replica la misma promoción adaptativa sobre el snapshot, por lo que
  acepta únicamente el conteo real de páginas producido por la nueva composición.
- Verificación: sintaxis JSX, 28 pruebas focalizadas y 260 pruebas completas pasan; 6 integraciones
  PostgreSQL se omiten sin credenciales. Falta la comprobación visual final dentro de InDesign.

## Bloque 2026-08-27: compatibilidad JSON para InDesign antiguo v1.29

- `ImportPerfectCatalog.jsx` ya no exige `JSON.parse`/`JSON.stringify` nativos. Incluye lector y
  escritor compatibles con motores ExtendScript antiguos; si el motor moderno existe, lo reutiliza.
- El fallback valida primero la gramática JSON y caracteres de control antes del `eval` aislado;
  rechaza expresiones, funciones o sintaxis ajena a JSON. El escritor escapa cadenas y serializa el
  reporte de preflight sin depender de librerías instaladas.
- Los paquetes InDesign nuevos incluyen automáticamente el JSX corregido. Los paquetes ya generados
  conservan la copia anterior y deben volver a generarse o sustituir su `ImportPerfectCatalog.jsx`.
- No requiere migración de PostgreSQL.
- Verificación: 28 pruebas focalizadas y 259 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales. Queda pendiente ejecutar el JSX corregido en la versión real de InDesign.

## Bloque 2026-08-27: orden editorial y campos HTML v1.28

- El selector visual incorpora una bandeja de referencias elegidas con acciones accesibles para
  subir, bajar o quitar. El orden de `selected_references` pasa a ser autoritativo y se conserva en
  preview, exportaciones y evidencia del manifiesto; sin selección explícita se mantiene el orden
  inmutable del release.
- El compositor permite mostrar u ocultar categoría, marca de producto, OEM, aplicaciones y motor
  en el catálogo HTML. La vista previa recibe los mismos controles y el borrador local los conserva.
- La generación HTML omite por completo etiquetas y contenedores desactivados, también dentro de la
  ficha ampliada porque esta reutiliza el contenido visible de la tarjeta. Los demás formatos no
  cambian su contrato en este bloque.
- El límite estructural del parser web sube de 20 a 32 campos manteniendo cuerpo máximo, campos
  exactos, rechazo de duplicados, CSRF y origen. No requiere migración.
- Verificación: sintaxis JavaScript, 58 pruebas focalizadas y 259 pruebas completas pasan; 6
  integraciones PostgreSQL se omiten sin credenciales.

## Bloque 2026-08-27: previsualización de identidad de marca v1.27

- Los formularios de identidad madre, marca nueva y revisión de marca muestran una composición
  inmediata con portada, ficha, referencia, aplicaciones, motor, acento secundario y marca de agua.
- Nombre, eslogan y cuatro colores se reflejan mientras se editan. El logo elegido se previsualiza
  mediante una URL `blob:` local y se revoca al reemplazarlo; no se carga al servidor hasta enviar el
  formulario auditado. Los logos actuales sirven como punto de partida.
- La interfaz calcula contraste texto/fondo y principal/fondo, muestra sus razones y advierte cuando
  no llegan a 4.5:1. La validación autoritativa del servidor permanece intacta.
- CSP amplía exclusivamente `img-src` para imágenes `blob:` generadas localmente; scripts, estilos,
  formularios y demás recursos conservan las restricciones previas. No requiere migración.
- Verificación: sintaxis JavaScript, 44 pruebas focalizadas y 258 pruebas completas pasan; 6
  integraciones PostgreSQL se omiten sin credenciales.

## Bloque 2026-08-27: selector visual de productos v1.26

- El compositor permite buscar y seleccionar visualmente productos de un release publicado. La
  búsqueda incluye referencia, nombre, categoría/tipo, aplicaciones, motor y marca vehicular;
  pagina 24 resultados y muestra la miniatura aprobada con `contain` cuando existe.
- Las casillas se sincronizan con `selected_references`, por lo que preview y exportación conservan
  la validación exacta, el límite y el checksum existentes. **Usar todos** vacía la selección explícita.
- La nueva lectura JSON es autenticada, de solo lectura, limita búsqueda/paginación y vuelve a
  validar el release completo antes de responder. Errores inesperados reciben diagnóstico seguro.
- Verificación: 57 pruebas focalizadas, sintaxis JavaScript y 258 pruebas completas pasan; 6
  integraciones PostgreSQL se omiten sin credenciales. No requiere migración.

## Bloque 2026-08-27: compositor web persistente v1.25

- La configuración de cada release se guarda automáticamente en `localStorage`: título, subtítulo,
  agrupaciones, filtros, referencias, densidad, plantilla y formatos. Al regresar se restaura sin
  guardar secretos, CSRF ni autorizaciones; **Restablecer** elimina únicamente ese borrador local.
- Un resumen vivo muestra agrupación, columnas, alcance de referencias y entregables seleccionados.
  El formulario continúa funcionando sin JavaScript o cuando el almacenamiento está deshabilitado.
- Se retiraron de la consola las paletas genéricas que aparentaban cambiar una marca ya congelada.
  La dirección visual informa ahora que logo, colores, tipografía y marca de agua provienen del perfil
  aprobado; `forest` permanece como respaldo técnico oculto para releases antiguos sin identidad.
- Verificación: JavaScript válido con `node --check` y 257 pruebas completas pasan; 6 integraciones
  PostgreSQL se omiten sin credenciales. No requiere migración.

## Bloque 2026-08-27: ficha ampliada en HTML v1.24

- Al tocar una fotografía del catálogo HTML se abre una ficha responsive con la imagen completa,
  referencia, nombre, categoría/marca, OEM, aplicaciones y motor disponibles.
- En escritorio la información ocupa un panel lateral; en móvil queda bajo la fotografía con
  desplazamiento propio. La imagen conserva `object-fit: contain` y nunca se recorta.
- El visor reutiliza la ficha y la imagen ya presentes en el documento: no duplica los Base64 del
  HTML autónomo, conserva búsqueda offline y funciona sin servicios externos.
- Verificación: 57 pruebas focalizadas y 257 pruebas completas pasan; 6 integraciones PostgreSQL
  se omiten sin credenciales. No requiere migración.

## Bloque 2026-08-27: dirección visual derivada de marca v1.23

- La paleta congelada de la marca del producto gobierna ahora la composición completa: principal,
  secundario, texto y fondo. El tema editorial queda como respaldo cuando el release no tiene perfil
  y ya no sustituye una identidad de marca disponible.
- El color secundario, antes almacenado pero sin uso efectivo, aparece como acento en portada y
  separadores de HTML, PDF, PowerPoint e InDesign. Las cuatro paletas de respaldo también definen
  un secundario explícito.
- La vista previa lee la identidad congelada del release y aplica sus cuatro colores mediante un
  script local con validación hexadecimal, compatible con la CSP estricta. El logo vehicular conserva
  su función limitada: acompañar el nombre del fabricante del automóvil, no dirigir el diseño.
- Verificación: 58 pruebas focalizadas y 257 pruebas completas pasan; 6 integraciones PostgreSQL
  se omiten sin credenciales. No requiere migración nueva.

## Bloque 2026-08-27: visor móvil sin duplicación v1.22

- El HTML digital usa un único visor nativo `dialog` reutilizable. Al tocar una miniatura toma la
  misma imagen ya cargada, la presenta completa con `contain` y permite cerrar con botón, fondo o
  tecla Escape.
- El HTML autónomo ya no repite cada URI Base64 para construir la ampliación. Cada fotografía
  optimizada aparece una sola vez en el archivo, reduciendo aproximadamente a la mitad la porción
  del peso atribuible a imágenes frente al visor anterior. Búsqueda y visor siguen offline.
- Verificación específica cubre fuente única incrustada, visor reutilizable y ausencia de recorte.

## Bloque 2026-08-27: logos de marcas vehiculares v1.21

- Migración forward-only `0016` amplía las revisiones visuales con alcance `vehicle_make` y exige
  exactamente un destino: empresa, marca de producto o marca vehicular. Conserva FK `RESTRICT`,
  historial append-only y permisos mínimos existentes.
- La pantalla **Marcas** enumera únicamente marcas vehiculares aprobadas y permite subir PNG, JPG o
  SVG seguro con sesión local, mismo origen, CSRF, confirmación y motivo. Cada cambio crea una
  revisión nueva; el archivo se guarda content-addressed y se verifica por SHA-256.
- Los releases nuevos congelan solamente los logos vehiculares usados por sus aplicaciones. El
  empaquetador verifica los activos y HTML/HTML autónomo, PDF, PowerPoint e InDesign los muestran
  junto al encabezado de la marca vehicular cuando esa es la agrupación. No aparecen en portada,
  marca de agua ni como sustituto de la marca del producto. PDF/PPTX requieren PNG/JPG; HTML e
  InDesign también conservan SVG.
- `ACTUALIZAR-SISTEMA.cmd` detecta `0016`. La reconstrucción controlada enlaza ahora el actualizador
  pendiente después del esquema base, corrigiendo además la omisión previa de `0015` en esa ruta.
- Verificación: 70 pruebas focalizadas y 257 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales. Para usar la pantalla se debe ejecutar una vez `ACTUALIZAR-SISTEMA.cmd`.

## Bloque 2026-08-27: tablero global responsive v1.20

- La portada del operador muestra un resumen actualizado de las cuatro etapas: archivos ingresados,
  identidades pendientes, imágenes por decidir/materializar y releases publicados o en borrador.
  Cada tarjeta es un acceso táctil directo y marca visualmente las etapas que requieren acción.
- El tablero se adapta de cuatro a dos y una columna; en móvil evita tablas y conserva objetivos
  interactivos amplios. Reutiliza consultas de solo lectura existentes y no requiere migración.
- Se uniformaron todos los fallos inesperados restantes de ingreso, revisión, imágenes, marcas,
  publicación, exportación y preflight: cada respuesta presenta un diagnóstico correlacionado sin
  exponer la excepción, mientras la consola registra operación, tipo y SQLSTATE.
- Verificación: 31 pruebas focalizadas y 254 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales.

## Bloque 2026-08-27: continuidad operativa e InDesign tipográfico v1.19

- La portada de Revisión ofrece ahora **Continuar donde quedaste**. Prioriza el primer plan con
  identidades pendientes y abre directamente su cola; cuando todos están resueltos conduce a
  Catálogos para construir la siguiente versión. Cada plan muestra progreso nativo accesible y una
  acción contextual: continuar revisión o diseñar catálogo.
- El componente es responsive, utiliza controles nativos compatibles con la CSP estricta y no
  aprueba, publica ni modifica datos automáticamente.
- Las lecturas principales de Revisión, Ingresos, Catálogos y Marcas generan ahora un identificador
  correlacionado de 12 caracteres ante fallos inesperados. El navegador no recibe SQL, rutas,
  credenciales ni el detalle interno; la consola conserva tipo de error y SQLSTATE para diagnóstico.
- `ImportPerfectCatalog.jsx` aplica las familias congeladas en el perfil del release: títulos en el
  peso Bold y cuerpo en Regular. Si InDesign no encuentra cualquiera de ellas, la añade al reporte
  `unavailable_fonts` en vez de sustituirla silenciosamente sin evidencia.
- Verificación: 32 pruebas focalizadas y 254 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales. Sigue pendiente validar visualmente un paquete real dentro de InDesign.

## Bloque 2026-08-27: búsqueda móvil y offline v1.18

- El HTML ligero y el autónomo incorporan un buscador interno fijo al desplazarse. Filtra en tiempo
  real por todo el texto editorial de cada ficha: referencia, nombre, categoría, marca, OEM,
  aplicaciones y motor; ignora mayúsculas y acentos.
- La búsqueda funciona completamente en el navegador, sin servidor, red ni envío de consultas. En
  móvil usa un campo de 48 px, teclado de búsqueda, contador de resultados y botón para limpiar.
- El catálogo oculta fichas y secciones sin coincidencias, conserva carga diferida de imágenes y el
  visor de fotografía completa. Los HTML ya exportados deben regenerarse.
- Verificación: 53 pruebas focalizadas y 252 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales.

## Bloque 2026-08-27: visor de imágenes del catálogo digital v1.17

- Cada fotografía del HTML ligero y del HTML autónomo es ahora pulsable y abre un visor a tamaño
  de pantalla. Tanto la miniatura como la ampliación usan encaje proporcional `contain`, por lo que
  muestran el producto completo sin recorte ni deformación.
- El visor funciona sin JavaScript mediante enlaces y `:target`: se cierra desde el botón visible o
  pulsando el fondo. Conserva accesibilidad por teclado, oculta la capa al imprimir y no cambia la
  política de seguridad ni la portabilidad del archivo autónomo.
- Los catálogos ya generados son inmutables y deben exportarse nuevamente para incluir el visor.
- Verificación focalizada: 53 pruebas pasan (exportación, operador y empaquetado). Suite completa:
  252 pruebas pasan y 6 integraciones PostgreSQL se omiten sin credenciales.

## Bloque 2026-08-27: auditoría técnica y visual

- Auditoría registrada en `docs/AUDIT-2026-08-27.md` con prioridades, decisiones y referencias
  oficiales W3C/Adobe.
- PDF/PPTX usan copias raster limitadas a su tamaño de presentación, con orientación EXIF, encaje
  proporcional y JPEG progresivo; los originales aprobados y el paquete InDesign siguen intactos.
  El último PDF anterior a esta corrección medía aproximadamente 105 MB y debe regenerarse para
  medir la reducción real.
- Los errores de imagen en PDF/PPTX ya no se omiten silenciosamente. InDesign TABLE respeta 12 pt y
  las fichas incluyen tipo de pieza y motor.
- La consola suma navegación por teclado visible, salto al contenido y objetivos de 44 px. Los
  perfiles nuevos validan contraste WCAG AA 4.5:1.
- Los manifiestos nuevos conservan conteos de productos con/sin imagen, imágenes únicas y bytes.

## Bloque 2026-08-27: preparación asistida y control de imágenes v1.14

- La revisión de imágenes ofrece **Aprobar y materializar coincidencias exactas**: una sola
  confirmación humana vuelve a contar hasta 500 candidatos, registra cada decisión y copia cada
  archivo después de verificar su SHA-256. Ambigüedades y conflictos continúan en revisión manual.
- Cada release nuevo congela `image_item_count` y `missing_image_item_count`. La pantalla de
  catálogos muestra ambos conteos y deshabilita composición/exportación cuando el snapshot tiene
  cero imágenes. La exportación operativa también lo rechaza en servidor con una explicación
  accionable; un release inmutable antiguo debe sustituirse por una versión nueva.
- El snapshot editorial incorpora `piece_type` y `engine_types` derivados de la categoría y de las
  aplicaciones aprobadas. Vista previa, HTML, PDF, PPTX y Data Merge/InDesign priorizan referencia,
  tipo de pieza, aplicaciones y motor, manteniendo fuera precio, moneda, inventario y cantidades.
- Paso manual para comprobar los 221 objetos ya materializados: reiniciar el revisor, abrir
  **Catálogos**, crear una versión nueva (por ejemplo `2026.27.08-r2`), publicar y exportar. El
  release anterior conserva cero imágenes por diseño y no se modifica.
- Verificación automatizada: 246 pruebas pasan; 6 integraciones PostgreSQL se omiten sin contraseña.
- Ajuste posterior de composición: las fotografías usan encaje proporcional completo en vista
  previa, HTML, PDF, PowerPoint e InDesign. Las cajas pueden dejar espacio libre, pero nunca recortan
  ni deforman el producto; PowerPoint calcula además el centrado para formatos extremos.
- La biblioteca de exportaciones ya no enumera cientos de objetos `IMAGE`: conserva su trazabilidad
  en el manifiesto y los paquetes, pero presenta una sola fila con cantidad y peso total. El HTML
  digital usa carga diferida nativa y decodificación asíncrona para no descargar de inmediato todas
  las fotografías de un catálogo extenso.
- El compositor ofrece **HTML autónomo** como entregable opcional. Incrusta las copias aprobadas como
  URI `data:` Base64 dentro de un único `.html`, conserva el HTML ligero como opción predeterminada
  y advierte que la variante autónoma puede pesar mucho y cargar todas las imágenes al abrirse.
- El HTML autónomo no incrusta ya el archivo original completo: crea en memoria una copia JPEG de
  pantalla limitada a 1200×900 px y calidad 82, respetando orientación y proporción. El original
  aprobado permanece intacto; CSS mantiene la fotografía completa, centrada y sin recorte.

## Bloque 2026-08-27: perfiles de marca v1

- Migracion forward-only `0013` crea perfiles de marca inmutables con codigo, nombre, eslogan, URL publica y paleta de cuatro colores; cada alta conserva operador y motivo. La aplicacion solo recibe `SELECT, INSERT`, sin UPDATE/DELETE.
- NATSUKI queda sembrada con perfil rojo/negro compatible con la direccion visual investigada.
- Nueva pantalla `Marcas` en la consola v1.12 permite crear perfiles con selector visual, sesion local, mismo origen, CSRF y confirmacion explicita. La URL opcional exige HTTPS y no admite credenciales.
- Nuevo launcher `MIGRAR-PERFILES-MARCA.cmd`; tambien se incorporo 0013 a la reconstruccion del limpiador de importaciones.
- Pendiente del mismo bloque: seleccionar el perfil antes del apply, eliminar la constante NATSUKI, incorporar logos mediante ingreso seguro y propagar los colores guardados a preview, HTML, PDF, PPTX e InDesign.
- Verificacion: 233 pruebas pasan; 6 integraciones PostgreSQL se omiten sin credenciales.
- Identidad NATSUKI confirmada para la siguiente iteracion: Barlow Condensed en titulares, DM Sans en cuerpo, ficha T1 a 12 pt con interlineado 1.8; logo de esquina y marca de agua opcional al 4-7%. Las fuentes no estan en el repositorio y no deben simularse ni descargarse sin validar los activos autorizados.
- Logo SVG maestro de NATSUKI incorporado desde `Z:\DOC MURILLO\logo nat.svg` sin modificar el original. Regla actualizada: 12 pt es minimo absoluto para todos los textos.
- Fuentes autorizadas recibidas e incorporadas con licencias OFL: Barlow Condensed Regular/Bold y DM Sans Regular/Bold. El PDF real ya registra y usa Barlow Condensed Bold en titulos, DM Sans en cuerpo y 12 pt/21.6 pt como minimo de cuerpo, referencias, metadatos y pies.

## Bloque 2026-08-27: PDF editorial v2

- Rediseñada la salida PDF con portada temática, edición, conteo e identidad del release; secciones
  numeradas; jerarquía propia para referencia, producto y datos técnicos; imágenes escaladas según
  densidad; encabezado, checksum abreviado, pie y numeración.
- La composición conserva temas y agrupación, muestra aplicaciones/OEM y sigue excluyendo campos
  comerciales y operativos. Continúa siendo prueba reproducible; PDF/X-4 final queda en InDesign.
- Verificación visual real: portada y página de fichas renderizadas a PNG sin cortes, solapamientos ni
  problemas de margen. Consola v1.11. Suite: 226 pruebas correctas, 6 integraciones omitidas sin clave.

## Bloque 2026-08-27: validación de imágenes por lote

- Consola operador v1.10 añade aprobación/rechazo atómico de hasta 500 asociaciones imagen–referencia
  pendientes. Reconsulta y bloquea el conjunto completo, compara el conteo esperado y conserva el
  hash individual de cada candidato en su decisión; cualquier cambio revierte todo el lote.
- La interfaz muestra el conteo pendiente y exige motivo más confirmación específica para aprobar o
  rechazar. La revisión individual permanece disponible para excepciones.
- El lote sólo decide asociaciones: no extrae, materializa ni publica fotografías.
- Suite: 226 pruebas correctas, 6 integraciones PostgreSQL omitidas sin contraseña.

## Bloque 2026-08-27: aplicaciones vehiculares de extremo a extremo

- Corregido el corte principal: `name_enrichment` ya no se pierde al aplicar. Los planes nuevos
  materializan fabricante, modelo y candidato de aplicación con años, posición, motores, confianza,
  regla y evidencia original; una marca no reconocida permanece vacía.
- La decisión de identidad resuelve atómicamente sus candidatos vehiculares visibles. Aprobar también
  aprueba el vocabulario pendiente utilizado; rechazar conserva el vocabulario y rechaza sólo las
  asociaciones del producto. La aprobación por filtro sigue limitada a 500 y audita cada identidad.
- Los releases incluyen `vehicle_makes`, `application_details` y etiquetas legibles. Vista previa,
  HTML, PDF, PPTX y Data Merge/InDesign muestran aplicaciones y permiten filtrar, agrupar o
  subagrupar por marca vehicular; productos multimarca aparecen en cada grupo correspondiente.
- El dry-run ahora ofrece **Verificar y preparar**: una confirmación ejecuta aprobación y aplicación
  como dos eventos dentro de una transacción. Publicar permanece separado.
- Añadida migración forward-only `0012` y `MIGRAR-APLICACIONES-VEHICULARES.cmd`. Debe aplicarse una vez
  en `perfect_catalog_dev` antes de probar un ingreso nuevo; requiere contraseña de `postgres`.
- Consola operador v1.9. Suite: 223 pruebas correctas, 6 integraciones PostgreSQL omitidas sin clave.

### Verificación manual pendiente

1. Ejecutar `MIGRAR-APLICACIONES-VEHICULARES.cmd` y confirmar `Resultado de psql: 0`.
2. Crear un dry-run nuevo; los planes ya aplicados antes de `0012` no contienen esos candidatos.
3. Abrir la cola, comprobar marca/modelo/años/motores y aprobar el filtro; construir un release nuevo.
4. Agrupar la vista previa por **Marca vehicular** y comparar varias referencias contra Odoo.

## Bloque 2026-08-27: inicio rápido y dirección visual

- Consola operador v1.8: `INICIAR-REVISOR.cmd` solicita únicamente la contraseña de PostgreSQL.
  Toma el usuario de Windows como actor, genera un código temporal de 72 bits, lo muestra sólo en
  consola y abre automáticamente `/operator/login` en el navegador predeterminado. No guarda
  credenciales ni coloca secretos en la URL; siguen disponibles los prompts manuales por CLI.
- Navegación reorganizada alrededor del flujo **Ingresar → Validar → Diseñar → Entregar**, conservando
  los accesos funcionales existentes, la sesión local, CSRF, cookies HttpOnly y auditoría.
- Catálogo digital HTML refinado con portada editorial, mejor espaciado, tarjetas, jerarquía de
  metadatos y comportamiento móvil, sin fuentes remotas ni JavaScript obligatorio.
- Añadido `docs/VISUAL_SYSTEM.md` con reglas compartidas para web/PDF/InDesign y referencias oficiales
  de Adobe para Data Merge, preflight, empaquetado, Output Preview y PDF/X-4. El perfil CMYK, sangrado
  y marcas quedan sujetos a la especificación real de la imprenta.
- Verificación: 219 pruebas pasan; 6 pruebas de integración PostgreSQL se omiten sin credenciales.

### Siguiente bloque recomendado

1. Crear presets visuales completos por marca y una previsualización comparativa T4/T2/T1/TABLE.
2. Añadir perfil de preflight de imprenta configurable y validar una exportación en Acrobat/InDesign.
3. Reducir pasos repetitivos dentro de la consola con un tablero de “continuar donde quedaste”.

## Sesión actual: Estudio visual de catálogos (2026-08-26)

### Resultado de esta sesión

- Alcance comercial simplificado por decisión del usuario: moneda, precios, inventario, UoM,
  responsable, etiquetas, favoritos, fechas operativas y `Imagen 128` quedan sólo en el XLSX/hash de
  origen. Nuevos dry-runs no los normalizan ni crean snapshots/medios; releases nuevos fijan esos
  campos a nulo y API v1.2, web y adaptadores de exportación los excluyen incluso al leer releases
  históricos. Las imágenes continúan únicamente por el workflow separado de originales aprobados.
- Parser vehicular v2 calibrado de forma agregada contra las muestras locales Perfect (896 filas) y
  PDM (154), sin copiar datos reales al repositorio. Añade perfiles de fuente, marcas/abreviaturas,
  años validados, cilindrada/códigos de motor con confianza diferenciada, posiciones canónicas, FMSI,
  referencias adicionales y corchetes PDM prudentes. El importador Natsuki incluye `name_enrichment`
  pendiente dentro de cada plan/fingerprint, pero apply/publicación aún no materializan inferencias.
  Las cantidades alternativas de PDM se ignoran deliberadamente según decisión del usuario.
- Consola operador v1.7 permite aprobar o rechazar en una sola transacción hasta 500 identidades
  pendientes del filtro actual. Exige motivo y confirmación específica, vuelve a consultar el conjunto,
  compara el conteo esperado y recalcula cada `review_sha256`; ante cualquier cambio revierte todo.
  Cada identidad conserva su propio evento de auditoría. El filtro desactiva restauración automática
  del navegador para que el selector visible corresponda a la consulta enviada.
- Consola operador v1.6 elimina el callejón sin salida posterior al dry-run: el enlace de Ingresos
  abre una inspección del UUID, alcance, versiones, hashes y fingerprint. Desde allí se puede aprobar
  y, en un segundo formulario explícito, aplicar el plan. Ambas transiciones conservan sesión local,
  CSRF, validación de origen, actor, motivo, confirmación y verificación criptográfica; aplicar sólo
  crea productos pendientes y conduce a la revisión individual.
- Nueva navegación `Catálogos` en la consola operador con listado de planes, releases y entregables.
- Construcción individual de borradores y publicación por checksum exacto desde formularios con sesión,
  Origin, CSRF, confirmación y actor derivado de la sesión; no existen acciones masivas.
- Configuración visual de título, subtítulo, agrupación, 1-3 columnas y formatos PDF/PPTX/InDesign JSON.
- Cada ejecución recibe UUID y directorio generado por el servidor. Las descargas autenticadas sólo
  admiten archivos enumerados por el manifiesto; rutas y nombres arbitrarios quedan rechazados.
- Historial local de exportaciones reconstruido desde manifiestos, sin depender de estado mutable web.
- Vista previa editorial de sólo lectura con agrupación y 1-3 columnas; valida el checksum completo,
  calcula conteos globales y limita el HTML a 24 fichas para escala de 25,000+ referencias.

### Pendiente siguiente

1. Reiniciar el revisor y probar la pantalla con un plan/release empresarial real.
2. Añadir filtros/agrupaciones multinivel y selección manual de productos.
3. Diseñar adaptadores de plantilla InDesign T4/T2/T1/TABLE/SEPARATOR y reporte de preflight.

### Avance InDesign del bloque

- Selector de perfil T4/T2/T1/TABLE incorporado al snapshot y a consola/CLI; valores desconocidos
  se rechazan antes de escribir archivos.
- El JSX crea páginas SEPARATOR por cambio de grupo, compone la densidad elegida y conserva perfil,
  release y checksum como etiquetas del INDD.
- Rutas de imagen sólo se aceptan relativas y sin `..`; se enlazan sin modificar el original.
- Cada INDD produce `perfect-catalog.indesign-preflight.v1` con imágenes faltantes, overflows y fuentes.
- Selección derivada por campo/texto y agrupación primaria/secundaria añadidas a preview, PDF, PPTX
  e InDesign; el manifiesto conserva conteo fuente, conteo seleccionado y criterios exactos.
- La consola de Ingresos permite indexar un ZIP de imágenes aceptado mediante POST individual con
  sesión/Origin/CSRF/motivo/confirmación. Muestra conteo, ambigüedades y hash; no extrae ni asocia.
- Preparada migración `0010` y núcleo `exact-approved-reference-v1`: candidatos deterministas por
  referencia primaria aprobada y decisiones humanas append-only con evidencia SHA-256 separada.
- Migración `0010` aplicada correctamente en `perfect_catalog_dev`; launcher
  `MIGRAR-REVISION-IMAGENES.cmd` conservado para otras instalaciones.
- Nueva cola `Imágenes`: generación exacta desde un índice concreto y aprobación/rechazo individual
  con sesión, Origin, CSRF, confirmación, motivo y hash de evidencia.
- Migración `0011` aplicada correctamente: materialización append-only e idempotente de decisiones
  aprobadas, con nueva verificación de ZIP, miembro, CRC, tamaño y SHA-256 antes de copiar.
- Las copias aprobadas se guardan content-addressed en `data/images/objects`; el ZIP de cuarentena
  permanece intacto y la aplicación no recibe permisos UPDATE/DELETE sobre la evidencia.
- Los releases nuevos capturan la imagen aprobada sin mutar releases anteriores. Cada exportación
  verifica de nuevo el SHA-256, empaqueta una copia autocontenida, la incluye en el manifiesto y
  entrega una ruta relativa segura al adaptador InDesign.
- PDF y PPTX colocan la copia empaquetada dentro de la ficha de producto. Una imagen que no pueda
  decodificarse degrada a ficha textual y no impide producir los demás entregables.
- La vista previa editorial muestra imágenes aprobadas mediante una ruta autenticada que vuelve a
  validar release, pertenencia, confinamiento de ruta y SHA-256 antes de servir cada archivo.
- La exportación permite seleccionar manualmente hasta 5.000 referencias exactas desde la consola
  o mediante `--reference` repetible en CLI. Se combina por intersección con el filtro opcional,
  rechaza referencias inexistentes y evita que un error tipográfico produzca un catálogo incompleto.
- El manifiesto y el snapshot InDesign conservan la lista canónica seleccionada; el manifiesto añade
  además su SHA-256 y el conteo exacto, de modo que la edición puede auditarse y reproducirse.
- Nuevo entregable `html`: catálogo digital responsive, portable y sin JavaScript, generado desde las
  mismas filas verificadas. Incluye portada, agrupaciones, 1-3 columnas, imágenes empaquetadas,
  versión y checksum del release, con escape estricto del texto procedente del snapshot.
- El HTML se selecciona desde la consola o con `--format html`, figura en el manifiesto SHA-256 y se
  descarga únicamente mediante la ruta autenticada ya limitada a archivos del manifiesto.
- Cada edición HTML produce además un `.digital.zip` determinista con `index.html` y todas sus
  imágenes verificadas. El ZIP figura como entregable separado con bytes y SHA-256, permitiendo
  trasladar o publicar el catálogo completo sin descargar assets uno por uno.
- Cuatro temas editoriales controlados (`forest`, `industrial`, `midnight`, `classic`) aplican una
  paleta consistente a HTML, PDF y PPTX; el valor también viaja en el layout InDesign.
- El manifiesto conserva ahora el layout completo (tema, títulos, agrupación, columnas y plantilla),
  además de selección y checksums; historiales anteriores sin layout siguen siendo compatibles.
- La vista previa editorial permite alternar los cuatro temas antes de exportar. Sólo acepta clases
  predefinidas servidas por el CSS local, por lo que no introduce estilos arbitrarios ni relaja CSP.
- Catálogo público renovado con tarjetas responsive de tres/dos/una columna, navegación por hasta 30
  categorías reales, búsqueda conservada al filtrar, marca, existencias e indicador visual de imagen.
- Las imágenes aprobadas del release se sirven en `/media/{product_id}` sólo después de revalidar
  pertenencia del producto, confinamiento bajo `data/images` y SHA-256. La ficha muestra además
  aplicaciones y referencias OEM con escape HTML.
- Nuevo `INICIAR-CATALOGO-PUBLICADO.cmd`: solicita la contraseña oculta y abre exclusivamente el
  último release publicado de NATSUKI; `INICIAR-SERVER.cmd` permanece como visor explícito del piloto.
- Verificación visual real completada en navegador integrado sobre los 893 productos del piloto XLSX:
  cuadrícula de escritorio, filtro `EMPAQUES / CARTER` con 15 resultados y breakpoint móvil de 390 px
  sin desbordamiento horizontal. El servidor temporal de prueba fue detenido al finalizar.
- La vitrina pública pagina en bloques de 48 productos: consulta sólo 49 filas para detectar si existe
  una página siguiente, conserva búsqueda/categoría en ambos sentidos y valida `page` entre 1 y 10000.
- Suite local actual: 201 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.
- Cada solicitud de `indesign-json` produce además un `.indesign.zip` determinista con
  `catalog.indesign.json`, imágenes verificadas, `ImportPerfectCatalog.jsx` e instrucciones.
- El JSX detecta automáticamente el snapshot adyacente al ejecutarse desde el paquete; si está
  instalado en el panel de Scripts conserva el selector de archivo. InDesign sigue sin acceder a BD.
- InDesign aplica ahora los cuatro temas editoriales permitidos mediante muestras RGB internas a
  portada, separadores, marcos de imagen, fichas y TABLE. Tema desconocido se rechaza.
- El INDD conserva `perfect_catalog_theme`; el preflight añade tema y conteos de grupos/páginas,
  además de imágenes faltantes, desbordamientos y fuentes no disponibles.
- Nuevo `verify-catalog-export MANIFEST`: validación offline sin contraseña que exige coincidencia
  exacta de directorio, bytes y hashes; inspecciona ZIP digital/InDesign, rutas, cifrado, tamaño
  descomprimido, archivos requeridos e imágenes. Devuelve `perfect-catalog.export-verification.v1`.
- PDF aplica el tema a jerarquía de portada y encabezados, añade regla editorial, versión, checksum
  abreviado y número de página. PPTX aplica la paleta a portada, fondos, títulos, subtítulo y fichas.
- QA visual real del PDF industrial completado en el visor integrado: portada de dos páginas sin
  recortes, título/subtítulo centrados, color temático, márgenes y pie legibles. Artefacto QA eliminado.
- Toda exportación InDesign genera además `*.datamerge.csv` y lo incluye como
  `catalog.datamerge.csv` en el paquete. Usa UTF-8 BOM, quoting CSV, listas unidas con `;`, campo
  relativo `@image` y neutralización de fórmulas para apertura segura en hojas de cálculo.
- La construcción de cualquier bundle ejecuta automáticamente `verify_catalog_bundle` después de
  escribir el manifiesto. Sólo retorna/mueve la exportación si archivos, hashes, ZIP e imágenes dan
  estado `verified`; CLI y operador reciben esa evidencia en el resultado.
- Cada descarga autenticada vuelve a comprobar que release, tamaño y SHA-256 coincidan con el
  manifiesto. Descargar el propio manifiesto verifica antes el bundle completo, incluidos sus ZIP.
- La pantalla Catálogos incorpora un tablero de producción en tres etapas —fuente, composición y
  biblioteca— con métricas de versiones, publicaciones y ediciones, más estados visuales de integridad.
- El compositor se divide en estructura, dirección visual y entregables. Temas, densidad y perfiles
  InDesign usan tarjetas radio nativas, accesibles y compatibles con CSP estricta sin JavaScript.
- El lanzador de vista previa rápida permite escoger categoría, densidad y tema; la página de control
  conserva después filtros y subagrupación, evitando previsualizar Bosque por error antes de exportar.
- Preview, HTML, PDF, PPTX e InDesign muestran ahora el mismo núcleo comercial cuando está disponible:
  referencia, nombre, categoría, marca, OEM y aplicaciones; los datos ausentes degradan sin inventarse.
- La vista previa alterna entre destino digital e InDesign y representa T4, T2, T1 y TABLE con
  densidades diferenciadas. Destino/perfil usan listas cerradas y los valores desconocidos devuelven 400.
- El preview InDesign representa portada y separadores y calcula páginas con la misma regla del JSX:
  una portada + un separador por grupo + `ceil(productos/capacidad)` reiniciado en cada grupo.
- Capacidades auditables: T4=4, T2=2, T1=1 y TABLE=16. Prueba Uvicorn/navegador: 12 productos,
  un grupo y TABLE mostraron correctamente 3 páginas estimadas.
- La biblioteca permite devolver el `*.preflight.json` generado por InDesign mediante carga individual
  con sesión, Origin, CSRF, confirmación y motivo. Límite 1 MiB y contrato JSON exacto.
- Antes de registrar, revalida todo el bundle y exige coincidencia de release, checksum, perfil, tema y
  productos. El recibo append-only queda fuera del bundle e incluye actor, fecha y SHA-256 del reporte.
- La consola muestra el último resultado: páginas, imágenes faltantes, overflows y fuentes. La prueba
  HTTP multipart real comprobó rechazo sin Origin y aceptación/redirección/estado con evidencia válida.
- Preview acepta título, subtítulo y hasta 5.000 referencias manuales exactas bajo el mismo contrato de
  exportación: normaliza duplicados, combina por intersección con filtros, conserva SHA-256 y rechaza
  cualquier referencia inexistente. La portada refleja esos valores antes de producir archivos.
- El compositor ofrece preview digital/InDesign de la configuración actual mediante JS externo self-only.
  Copia una allowlist de campos editoriales; nunca incluye CSRF, confirmación ni opciones mutantes. Sin JS,
  el launcher GET básico y el POST de exportación continúan operativos.
- El receptor de preflight deriva grupos y páginas desde el snapshot InDesign verificado y exige igualdad
  exacta con `group_count`/`page_count`; no acepta sólo conteos plausibles. Clasifica `passed` o `issues`.
- La biblioteca distingue `Sin incidencias`/`Con incidencias` y permite descargar el recibo JSON mediante
  una ruta autenticada limitada a UUID de release, exportación y recibo. UUID ajeno devuelve 404.
- El JSX deja de heredar preferencias del puesto: fija A4 vertical, puntos, origen por página, páginas no
  enfrentadas y sangrado uniforme de 3 mm antes de crear marcos. El INDD conserva formato/sangrado en labels.
- Corregido el fallo real de `Promover a dry-run`: una transacción SERIALIZABLE permanecía abierta mientras
  otra conexión creaba el plan, por lo que el snapshot inicial no podía verlo al insertar la FK de `0008`.
- La exclusión usa ahora advisory lock de sesión en una conexión autocommit; la lectura termina antes del
  dry-run y la escritura final abre un snapshot nuevo. Fallos inesperados muestran/loguean un ID correlacionado
  de 8 hex sin exponer el texto crudo de la excepción.
- Suite local actual: 217 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

## Sesión actual: Login estable y primer flujo de catálogo/InDesign (2026-08-26)

### Resultado de esta sesión

- Login operador corregido para Edge, Chrome y clientes integrados: cookie de challenge con alcance
  `/operator`, parseo estricto, compatibilidad segura Origin/Referer+Sec-Fetch-Site y diagnósticos
  separados para origen, challenge, código y límite de intentos, sin revelar ni registrar el código.
- Prueba HTTP real levanta Uvicorn en `127.0.0.1` y valida GET, cookie HttpOnly, CSRF, POST y redirección
  303 a `/operator`. El flujo TCP fue verificado; no había navegador integrado conectado para una
  comprobación visual automatizada.
- Añadido restablecimiento interactivo de contraseña para `perfect_catalog_app` mediante
  `RESTABLECER-CONTRASENA-REVISOR.cmd`; no conserva credenciales en archivos, argumentos o variables.
- Nuevo `export-catalog`: sólo acepta releases `published`, revalida todos sus hashes y genera PDF,
  PPTX, snapshot `perfect-catalog.indesign-snapshot.v1` y manifiesto SHA-256 sin sobrescribir destinos.
- Primer puente InDesign en `indesign/ImportPerfectCatalog.jsx`: abre el snapshot, valida publicación,
  crea portada y fichas editables, conserva UUID/checksum dentro del INDD y reporta desbordamientos.
- `0008` y `0009` aplicadas en `perfect_catalog_dev`. `0008` quedó reanudable y valida una tabla
  preexistente antes de completar índice, trigger y permisos; su lanzador conserva diagnóstico seguro.
- Verificación manual completada en Edge/Chrome local: el código temporal redirige a `/operator`.
  `Referrer-Policy: same-origin` permite el fallback Chromium sin divulgar referentes a otros orígenes.
- Suite local: 174 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Ejecutar las 6 integraciones PostgreSQL opt-in ahora que el esquema local está actualizado.
2. Probar un release empresarial publicado con `export-catalog` y abrir el JSON generado en InDesign.
3. Sustituir la maqueta básica JSX por adaptadores de plantilla T4, T2, T1, TABLE y SEPARATOR, con
   resolución revisada de imágenes/fuentes y reporte persistente de preflight.

## Sesión Actual: Índice no destructivo de imágenes (2026-08-26)

### Resultado de esta sesión

- Añadido `index-images` para submissions `image_archive` aceptados: exige actor, motivo y contraseña,
  y revalida ruta, tamaño y SHA-256 antes y después de recorrer el ZIP.
- El índice lee cada imagen por streaming sin extraerla y conserva ruta, MIME, tamaños, CRC32,
  SHA-256 de contenido y clave normalizada de búsqueda.
- Colisiones de nombre quedan `ambiguous`; entradas únicas permanecen `unmatched`. No existe matching
  automático ni escrituras en `media_asset`, `product_media` o productos.
- Migración forward-only `0009` crea cabecera/entradas append-only, contexto exacto submission/asset/hash
  y permisos mínimos `SELECT`/`INSERT`; launcher `MIGRAR-INDICE-IMAGENES.cmd` añadido.
- Suite local: 164 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Aplicar `0008` y `0009` en orden y ejecutar integraciones reales con fixtures sintéticos.
2. Exponer la indexación como POST individual en la consola operador, sin acción masiva.
3. Diseñar candidatos de asociación imagen-producto separados, siempre pendientes de revisión humana.
4. Añadir solicitud operador para exportar PDF/PPTX desde releases publicados.

## Sesión Actual: Promoción individual en consola operador (2026-08-26)

### Resultado de esta sesión

- Consola operador v1.2 muestra promociones existentes y ofrece `Promover a dry-run` sólo para
  submissions Odoo aceptados que todavía no tengan un plan enlazado.
- Nueva ruta exclusivamente POST individual con sesión, Origin, CSRF, campos exactos, motivo de
  4-500 caracteres y confirmación. No existe GET mutante ni acción masiva.
- El gateway conserva la contraseña sólo en memoria y ejecuta perfilado/dry-run fuera del event loop;
  el actor procede de la sesión firmada, no del formulario.
- El historial enlaza el plan creado y comunica que permanece pendiente de revisión.
- Suite local: 157 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Aplicar `0008` con `MIGRAR-PROMOCIONES.cmd` y probar la ruta con PostgreSQL real.
2. Construir el índice no destructivo de imágenes sobre ZIP validado en cuarentena.
3. Añadir una solicitud operador separada para exportar PDF/PPTX desde releases publicados.

## Sesión Actual: Promoción explícita de cuarentena (2026-08-26)

### Resultado de esta sesión

- Implementado `promote-intake` para datos Odoo aceptados: exige UUID, actor, motivo y contraseña;
  revalida ruta, tamaño y SHA-256 antes de copiar o procesar.
- Perfilado, sugerencias flexibles de columnas y dry-run quedan encadenados sólo por acción explícita.
  El resultado sigue en `awaiting_review`; no existe aprobación, apply o publicación automática.
- Migración forward-only `0008` añade evidencia append-only con relaciones exactas entre submission,
  asset/hash y batch/plan, más permisos `SELECT`/`INSERT` mínimos para la aplicación.
- Copia aislada y trazable bajo `data/intake/processing`; el objeto content-addressed original nunca
  se modifica. Promociones repetidas son idempotentes y las concurrentes usan advisory lock.
- Documentación operativa y launcher `MIGRAR-PROMOCIONES.cmd` añadidos.
- Suite local: 156 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas hasta aplicar `0008`.

### Pendiente siguiente

1. Aplicar `0008` en `perfect_catalog_dev` y ejecutar la integración real con un fixture sintético.
2. Exponer la promoción como POST individual en la consola operador, con CSRF, confirmación y motivo;
   no añadir acciones masivas.
3. Construir el índice no destructivo de imágenes sobre ZIP validado en cuarentena.

## Sesión Actual: Parser y exportaciones verificadas (2026-08-26)

### Resultado de esta sesión

- Portado selectivamente un parser puro de nombres y aplicaciones vehiculares; toda salida conserva
  procedencia/versionado y queda en `pending_review`, sin escrituras ni publicación automática.
- Añadida detección auxiliar de aliases de columnas, delimitadores y UTF-8/Windows-1252. No sustituye
  el contrato Odoo ni su validación de identidad y queda preparada para el futuro flujo explícito de
  promoción desde cuarentena.
- Añadido adaptador de exportación que revalida definición, snapshots, hashes individuales y hash
  agregado de un release antes de exponer filas a cualquier motor.
- Generadores PDF y PowerPoint desacoplados con portada, agrupaciones, branding básico, OEM,
  aplicaciones y diseños de 1-3 columnas. No consultan PostgreSQL ni datos empresariales.
- Dependencias fijadas: `reportlab==4.4.3` y `python-pptx==1.0.2`.
- Suite: 149 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas. Línea base anterior:
  143 aprobadas y las mismas 6 opt-in omitidas.

### Pendiente siguiente

1. Diseñar la promoción explícita desde cuarentena a perfilado/dry-run e integrar allí las
   sugerencias tabulares, sin importación automática.
2. Añadir una acción operador separada para solicitar exportaciones de releases publicados y una
   política de destino/nombres en `data/exports`; este bloque sólo aporta motores puros.
3. Ampliar el diccionario del parser únicamente con fixtures revisados y definir el workflow humano
   que convierte sugerencias en aplicaciones aprobadas.
4. Ejecutar las 6 integraciones opt-in al disponer de la contraseña local en el flujo protegido.

## Sesión Actual: Centro web de ingreso protegido (2026-08-24)

### Resultado de esta sesión

- Centro de ingreso añadido a `http://127.0.0.1:8081/operator/intake` dentro de la sesión operador;
  recibe Odoo XLSX/CSV/TSV, manual PDF y paquetes ZIP de imágenes o InDesign.
- Migración forward-only `0007`: `intake_asset` deduplica objetos por SHA-256 y
  `intake_submission` conserva cada evento; ambas tablas son append-only y el rol de aplicación
  sólo recibe `SELECT`/`INSERT`.
- Cuarentena local content-addressed en `data/intake`, excluida de Git; nombres recibidos nunca se
  convierten en rutas y una carga no ejecuta importación, extracción, apply ni publicación.
- Límites por tipo, `Content-Length`, multipart acotado, filename seguro, firma básica, SHA-256,
  ZIP traversal/enlaces/cifrado/expansión, ejecutables bloqueados y compensación ante fallo de BD.
- Historial paginado y filtrable con actor, motivo, hash, duplicados y causa de rechazo. Los bytes
  rechazados se borran; su evidencia permanece en PostgreSQL.
- `MIGRAR-INGRESOS.cmd` aplica `0007` y `docs/INTAKE_WORKFLOW.md` documenta operación, backup,
  alcance de cuarentena y la separación del procesamiento posterior.

- Consola Jinja2 separada implementada en `http://127.0.0.1:8081/operator`; el catálogo piloto de
  `INICIAR-SERVER.cmd` permanece intacto y de solo lectura en el puerto 8080.
- Nuevo `INICIAR-REVISOR.cmd`: solicita contraseña PostgreSQL, actor auditable y código temporal;
  valida la conexión antes de escuchar y nunca admite un host distinto de localhost.
- Cola set-based paginada (50 por página) con búsqueda, filtros y conteos; elimina el N+1 anterior
  y conserva el inspector CLI completo con su límite explícito de 5,000.
- Sesión en memoria de una hora, PBKDF2, límite de intentos, cookies firmadas HttpOnly/Strict, CSRF
  de login y sesión, validación Origin, formularios limitados, Jinja autoescape y CSP/no-store.
- Decisiones únicamente por POST individual con motivo; no existen GET mutantes, aprobación masiva,
  OpenAPI ni rutas de catálogo público en el proceso operador.
- Pruebas HTTP cubren autenticación, expiración, manipulación de cookie, CSRF, origen, XSS, cabeceras
  y separación de superficies. Integración real valida paginación/búsqueda como rol de aplicación.
- `VALIDAR-BLOQUE.cmd` permite repetir en una consola visible la suite PostgreSQL y el dry-run real
  sin escribir credenciales en argumentos, variables o archivos.

- Workflow `inspect-reviews` / `review-product` implementado para decisiones individuales con
  fingerprint del plan, `review_sha256` por ficha, actor y motivo obligatorios.
- Aprobación y rechazo actualizan atómicamente producto y referencia primaria; una decisión previa
  no puede sobrescribirse y el reintento idempotente exige el mismo hash guardado en auditoría.
- Migración forward-only `0006` aplicada: protege datos de identidad, limita UPDATE por columna y
  valida al final de la transacción que producto y referencia tengan estados coherentes.
- El constructor de releases ahora rechaza una marca completa si conserva identidades pendientes;
  ya no puede omitirlas silenciosamente y publicar un subconjunto accidental.
- La cola CLI tiene un límite explícito de 5,000 identidades; no trunca. La consola web ya pagina
  por consulta para la escala objetivo.
- `INICIAR-SERVER.cmd` abre el visor XLSX actual en `http://127.0.0.1:8080/`; todavía no presenta la
  cola PostgreSQL ni acciones de revisión.

- Auditoría provisional documentada en `docs/STATUS_AUDIT_V2_2.md`.
- Bloqueo exacto: no se recibió `Manual_Desde_Cero_Perfect_Trading_Natsuki_v2.2.pdf`; solo llegó
  el texto del encargo. La conformidad literal con el manual no puede cerrarse hasta adjuntarlo.
- API FastAPI v1.2 de solo lectura implementada sin retirar el visor existente.
- El origen predeterminado es el último `catalog_release` publicado de una marca; búsqueda,
  categorías y detalle permanecen encerrados en ese release.
- Las URLs y respuestas publicadas usan UUID estable de variante o template. Los IDs
  `source-row:*` quedan limitados y rotulados como modo piloto XLSX explícito.
- Cada snapshot valida schema, identidad y hash canónico; el hash agregado valida marca, versión,
  orden e inventario completo de items antes de servir cualquier consulta.
- Workflow `build-release` / `inspect-release` / `publish-release` / `archive-release` implementado
  con actor, motivo, fingerprint/checksum exactos, transacciones serializables e idempotencia.
- La construcción exige plan aplicado, productos activos y una referencia interna primaria
  aprobada por identidad; aplicar datos nunca activa ni publica automáticamente.
- `catalog-release-v2` compromete criptográficamente también la definición y selección del release.
- La migración forward-only `0005` fue aplicada: triggers protegen releases, items y auditoría como
  append-only; solo permiten `draft → published → archived` y permisos mínimos por columna.
- `perfect-catalog-api` arranca el origen publicado por defecto. `INICIAR-SERVER.cmd` conserva el
  piloto local al pasar explícitamente `--source-dir data\imports`.
- Empaquetado corregido: `tools.odoo_profiler` funciona fuera de la raíz del repositorio.
- `.env.example` corregido para no presentar SQLite como base de desarrollo.
- Prueba de humo real: XLSX maestro de 893 filas, API devuelve catálogo y fichas correctamente.
- Contrato/importador v0.2: ya no exige 893 filas ni 13 columnas en orden exacto; acepta
  reordenamiento, conserva columnas nuevas y reporta opcionales ausentes, con límite de piloto.
- Segunda muestra real verificada: 237 filas y solo 2 columnas críticas, sin inventar opcionales.
- Workflow `approve-plan` / `apply-plan` implementado con actor, motivo y fingerprint obligatorios.
- El apply recalcula hashes, verifica el archivo, bloquea el plan y usa una transacción serializable;
  un segundo intento sobre un plan aplicado responde `already_applied` sin repetir escrituras.
- Alcance seguro actual: altas, snapshots completos, `no_change` y medios marcados pendientes. Las
  operaciones `update`, `blocked` y `conflict` se rechazan antes de escribir.
- `0003` fue aplicada en `perfect_catalog_dev`; flexibiliza el conteo opcional de variantes y limita
  por columna las transiciones permitidas al rol de aplicación.
- `0004` fue creada y aplicada forward-only para corregir drift de lectura con mínimo privilegio:
  `perfect_catalog_app` recibe SELECT solo en las 18 tablas que consume actualmente.
- Integración real como `perfect_catalog_app`: aprobación, alta, snapshot con -2/0, auditoría,
  reintento `already_applied`, permisos y rollback transaccional verificados.
- Integración del read model como `perfect_catalog_app`: selección, búsqueda, categorías, ficha por
  UUID y detección de manipulación, todo con datos sintéticos y rollback.
- Integración completa como rol real: apply sintético, activación/revisión sintética, build,
  checksum erróneo, publicación, lectura UUID, archivo, reintentos e inmutabilidad con rollback.
- Pruebas: 143 descubiertas y 143 aprobadas, incluidas las 6 integraciones PostgreSQL.
- Dry-run real v0.3 repetido: 893 filas, 2,497 items, archivo intacto y 0 escrituras empresariales.
- Ningún plan real fue aprobado/aplicado ni se publicó un release empresarial; no se modificó Odoo
  ni el Excel fuente y las ocho tablas empresariales siguen vacías.

### Próxima etapa por dependencias

1. Añadir una promoción explícita desde cuarentena hacia perfilado/dry-run; la recepción nunca debe
   importar automáticamente.
2. Construir el índice no destructivo de imágenes sobre un ZIP de cuarentena validado.
3. Añadir reconciliación `update` campo por campo cuando una exportación completa aporte identidad
   Odoo estable; hasta entonces permanece bloqueada por diseño.
4. Continuar con catálogo enriquecido y PWA/offline sobre releases inmutables.

### Sesión anterior: Inicialización del Proyecto (2026-08-17)

### Estado de Cumplimiento ✓

- ✓ Diagnóstico del entorno completado
- ✓ Repositorio Git inicializado
- ✓ Documentación base creada
- ✓ Estructura de carpetas planificada
- ✓ Reglas no negociables documentadas
- ✓ Muestra real de Odoo analizada preliminarmente
- ✓ Schema y migración validados en PostgreSQL
- ✓ Dry-run de Natsuki ejecutado sin escrituras empresariales
- ✓ MVP web local de consulta sobre la muestra funcionando
- ✓ Visor local detecta automáticamente el XLSX más reciente en `data/imports`
- ✓ Ficha individual web y ficha imprimible funcionando

### Completado en Esta Sesión

1. **Diagnóstico de Entorno**
   - Windows 11 Pro (Build 26200) - 64 bits
   - 237.41 GB libres en C:\
   - VS Code 1.133.0
   - Git 2.54.0
   - Python 3.14.5 disponible
   - Adobe InDesign 2026 presente
   - PostgreSQL y pgAdmin: NO instalados (fase posterior)

2. **Inicialización de Repositorio**
   - git init ejecutado
   - .gitignore configurado
   - Archivos de documentación creados:
     - PROJECT.md
     - AGENTS.md
     - HANDOFF.md (este archivo)
     - README.md
     - .env.example

3. **Documentación y validación**
   - Reglas no negociables documentadas
   - Estructura organizativa: empresa, marcas, fuente maestra
   - Funcionalidades: búsqueda, filtrado, generación de catálogos
   - Formatos de salida: web, PDF, InDesign
   - `docs/DATA_SPEC.md`: perfil preliminar de la muestra de 893 filas
   - Plan de importación persistido en `awaiting_review`

### Próximos Pasos (Orden de Prioridad)

#### FASE 1: Análisis de Datos (PRELIMINAR COMPLETADO)
- [x] Analizar muestra real de Excel de Odoo (Natsuki / Empaques)
- [x] Analizar estructura de columnas y completitud
- [x] Documentar campos observados en DATA_SPEC.md
- [ ] Obtener exportación completa de Odoo para ampliar la evidencia
- [ ] Identificar relaciones OEM, cross-reference, FMSI y aplicaciones vehiculares
- [ ] Convertir la especificación preliminar en contrato definitivo tras recibir más exportaciones

**Responsable**: Analista de Datos / Odoo  
**Dependencias actuales**: Exportación completa y/o nuevas muestras de Odoo

#### FASE 2: Diseño y Validación de Base de Datos
- [x] Diseñar schema de PostgreSQL preliminar
- [x] Definir tablas, relaciones, constraints e índices
- [x] Validar DDL y migración en PostgreSQL
- [ ] Revisar ajustes del schema contra la exportación completa

**Responsable**: Coordinador + Ingeniero Backend  
**Dependencias**: DATA_SPEC.md  
**Bloqueado por**: FASE 1  

#### FASE 3: Importador de Datos (Dry-run preliminar)
- [x] Importador Python para la muestra Excel/CSV
- [x] Validaciones, staging y resultados separados
- [x] Plan persistido con hash canónico y compuerta de aprobación
- [x] Control de imágenes sin decodificar ni modificar originales
- [ ] Ampliar reglas con la exportación completa de Odoo

**Responsable**: Ingeniero Backend  
**Dependencias**: Schema de BD  
**Bloqueado por**: FASE 2  

#### FASE 4: API Base
- [x] Búsqueda local por referencia y nombre
- [x] Filtro local por categoría
- [x] API HTTP formal con endpoints JSON
- [x] Read model publicado con UUID y checksum
- [ ] Endpoints de agrupación multinivel

**Responsable**: Ingeniero Backend  
**Dependencias**: BD con datos + Importador  
**Bloqueado por**: FASE 3  

#### FASE 5: Interfaz Web Local
- [x] Búsqueda por referencia y nombre
- [x] Filtro inicial por categoría
- [ ] Filtros multi-nivel
- [ ] Agrupación dinámica
- [x] Visualización de resultados de ficha básica

**Responsable**: Ingeniero Frontend  
**Dependencias**: API  
**Bloqueado por**: FASE 4  

#### FASE 6: Exportación de PDFs
- [ ] Generador de fichas PDF
- [ ] Compilación de catálogos PDF
- [ ] Metadatos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD con datos + API  
**Bloqueado por**: FASE 3  

#### FASE 7: Integración InDesign
- [ ] Scripts de InDesign
- [ ] Plantillas T4, T2, T1, TABLE, SEPARATOR
- [ ] Generación de documentos INDD
- [ ] Control de imágenes, fuentes, desbordamientos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD + Exportación PDF  
**Bloqueado por**: FASE 6  

### NO Hacer Todavía

- ❌ Ejecutar APPLY sin revisión y aprobación humana explícita
- ❌ Tratar la muestra de 893 filas como el catálogo completo
- ❌ Declarar definitivo el contrato del importador con la evidencia actual
- ❌ Tocar fotografías originales
- ❌ Modificar el Excel maestro de muestra

### Decisiones de Arquitectura Cerradas

| Decisión | Estado | Definición |
|----------|--------|------------|
| Base de datos | Cerrada | PostgreSQL es la base oficial. SQLite no será la base principal y solo podría usarse para pruebas aisladas si fuera necesario. |
| Backend | Cerrada | FastAPI es el backend oficial. |
| Frontend inicial | Cerrada | Jinja2 + HTML + CSS + JavaScript. React no se utilizará inicialmente. |
| Evolución | Cerrada | La arquitectura podrá evolucionar hacia un frontend separado si una necesidad real lo justifica. |

El frontend inicial debe ofrecer una interfaz premium, responsive y moderna. La ausencia inicial de React reduce complejidad y no limita el diseño.

### Decisiones Pendientes

| Decisión | Estado | Notas |
|----------|--------|-------|
| Formato Snapshots InDesign: XML vs JSON | Pendiente | Definir tras primer análisis de datos |
| Control de Versiones de Catálogos | Parcialmente cerrada | Releases inmutables, versionados y con checksum; falta definir la política operativa de publicación y retención. |

### Notas Técnicas

- Ruta del proyecto: `C:\PERFECT_CATALOG`
- MVP local: `http://127.0.0.1:8080`
- Lanzamiento: `INICIAR-SERVER.cmd` o `scripts/run_catalog_web.py`
- El MVP lee el Excel de muestra en modo solo lectura; no requiere contraseña ni conexión a PostgreSQL
- Al copiar una nueva exportación `.xlsx` a `data/imports`, el visor la recarga automáticamente en la siguiente consulta
- Ficha web: `/producto/<fila>`; versión imprimible: `/producto/<fila>/ficha`
- La ficha imprimible se puede guardar como PDF desde el navegador; no genera aún un PDF automatizado
- Usuario propietario: AzureAD\Diseño2
- Política de ejecución PowerShell: Bypass
- No se ejecuta como administrador (OK, no requerido)

### Contactos y Escalaciones

- **Bloqueos con Excel**: Contactar a Área de Odoo
- **Decisiones estratégicas**: Revisar con Gerencia
- **Cambios en reglas de negocio**: Actualizar PROJECT.md inmediatamente

### Última Actualización

- **Fecha**: 2026-08-17
- **Sesión**: Inicialización
- **Duración**: ~1 hora diagnóstico + setup
- **Próxima Revisión**: Tras obtener Excel de Odoo

---

### Cómo Usar Este Archivo

1. **Al Iniciar Sesión**: Lee este archivo completo
2. **Identifica Bloqueadores**: Busca items con ❌ o "Pendiente"
3. **Continúa desde Último Checkpoint**: Busca checkboxes [ ] sin marcar
4. **Antes de Cerrar Sesión**: Actualiza este archivo con tu progreso
5. **Comenta Decisiones**: Explica el "por qué" no solo el "qué"
## 2026-08-27 - Limpieza guiada de importaciones

- Se agrego `LIMPIAR-IMPORTACIONES.cmd` para empezar de cero sin reinstalar PostgreSQL ni cambiar usuarios o contrasenas.
- La herramienta exige cerrar el revisor, escribir `LIMPIAR IMPORTACIONES` y proporcionar la contrasena de PostgreSQL una sola vez.
- Antes de limpiar crea un `pg_dump` y mueve `data/imports`, `data/intake`, `data/images` y `data/exports` a `data/backups/limpieza-<fecha>`; no borra respaldos anteriores.
- Reconstruye el esquema `perfect_catalog` y reaplica en orden las migraciones 0001-0012, eliminando importaciones y derivados sin dejar referencias huerfanas.
- La limpieza no se ejecuta durante desarrollo ni pruebas: solo se realiza al abrir voluntariamente el nuevo lanzador y confirmar.
- Verificacion real: la limpieza del 2026-08-27 creo un dump PostgreSQL valido de 138 MB y archivo 104 elementos (aprox. 275 MB) en `data/backups/limpieza-20260827-092235`; las cuatro carpetas activas quedaron vacias.
- Se corrigio el limpiador para conservar `.gitkeep` sin modificarlo en futuras ejecuciones.

## Proximo bloque acordado - Perfiles de marca y direccion visual

- La referencia visual objetivo admite portada de marca, cuadricula de productos y ficha individual para PDF/InDesign.
- La consola solo ofrece actualmente cuatro paletas fijas (`forest`, `industrial`, `midnight`, `classic`); todavia no guarda colores o logos por marca.
- Bloqueo funcional confirmado: `application.py` materializa altas nuevas con la constante `NATSUKI`. El campo Marca al construir un release resuelve una marca existente, no es un alta de marca.
- Implementar antes del siguiente catalogo multimarca: migracion de perfil de marca, pantalla `Marcas`, alta/edicion auditada de nombre/codigo/logo/eslogan/colores, seleccion de marca al preparar la importacion y propagacion exacta a PDF, HTML, PPTX e InDesign.
- Investigación visual y funcional documentada en `docs/DIRECCION-VISUAL-CATALOGOS.md`, con referencias de NSK, ZF, HELLA, Parker Racor, Brembo, TecDoc y Adobe InDesign.
- Sistema de páginas definido: portada P0, separador S, cuadrículas T4/T2, ficha T1 y guía técnica TABLE.

## 2026-08-27 - Marca vinculada y sistema editorial 1-4

- La migración `0014_brand_profile_workflow.sql` vincula cada plan y marca materializada con un perfil visual: tipografías, mínimo 12 pt, interlineado 1.8, logo de esquina y marca de agua configurable (4-7%).
- `MIGRAR-MARCA-CATALOGO.cmd` aplica el cambio en Windows y debe ejecutarse una vez antes de preparar una importación nueva.
- El dry-run exige elegir la marca. La selección se audita, se materializa y queda congelada en el release; las altas ya no usan una constante NATSUKI.
- PDF, HTML digital, PPTX e InDesign reciben el perfil inmutable. Natsuki usa su paleta, Barlow Condensed, DM Sans, logo oficial y marca de agua.
- Sistema: P0 portada, S separador automático, T4 (4 fichas), T2 (2), T1 (1) y TABLE (10 filas legibles a 12 pt). El ZIP InDesign incluye logo y `Document fonts`.
- QA visual: PDF Natsuki T2 renderizado a PNG e inspeccionado en portada y página de producto.
- Suite completa: 237 pruebas aprobadas y 6 omitidas de PostgreSQL opt-in.
- Corrección operativa: el lanzador 0014 detecta si falta `brand_profile`, aplica primero 0013 con la misma sesión de `psql` y omite de forma segura cualquiera de las dos migraciones que ya esté instalada.
- Corrección PostgreSQL: la restricción de `logo_asset_key` usa `[.]svg`, evitando el doble escape que rechazaba la ruta válida `brands/natsuki/logo.svg`; el intento fallido quedó revertido por la transacción.
- Corrección de inspección: la consulta del plan agrupa explícitamente el perfil de marca unido. El error anterior se mostraba incorrectamente como “PostgreSQL no disponible”; ahora se registra y presenta un identificador diagnóstico seguro.
- Diagnóstico de imágenes: las excepciones inesperadas al aprobar una asociación individual o un lote ahora se registran en la consola con un identificador seguro que también aparece en la pantalla; no se muestran referencias, hashes ni credenciales.
- Aprobación en lote de imágenes corregida: `FOR UPDATE` exigía un permiso incompatible con la tabla append-only. Se reemplazó por `pg_advisory_xact_lock` dentro de la transacción serializable; se conservan permisos mínimos y la comprobación del conjunto pendiente exacto.
- Auditoría preventiva de permisos: decisión individual y materialización tenían el mismo riesgo sobre evidencia append-only. Ambas usan ahora bloqueos advisory por candidato y no requieren ampliar permisos `UPDATE`.
- Construcción de release: los valores numéricos del perfil visual provenientes de PostgreSQL se convierten a JSON canónico antes de calcular y persistir el snapshot. Se evita que `Jsonb` rechace objetos `Decimal`; la ruta incluye diagnóstico seguro.

## 2026-08-27 - Operación simplificada y auditoría preventiva

- La carpeta raíz expone un solo actualizador: `ACTUALIZAR-SISTEMA.cmd`. Detecta y aplica en orden únicamente los bloques pendientes 0007–0015; si el esquema base no existe se detiene sin reconstruir ni borrar datos.
- Se retiraron los ocho lanzadores públicos `MIGRAR-*`. Los SQL históricos y bootstrap internos permanecen versionados para trazabilidad y reconstrucción controlada.
- Regla operativa: el usuario trabaja con `INICIAR-REVISOR.cmd`; ejecuta `ACTUALIZAR-SISTEMA.cmd` únicamente después de recibir código nuevo que cambie la base o cuando la consola indique que falta una actualización.
- Imágenes: la consola permite materializar en lote hasta 500 asociaciones aprobadas, verificando el conjunto exacto y cada SHA-256. Después debe construirse una versión nueva porque los releases anteriores son inmutables.

## 2026-08-27 - Identidad madre y activos visuales por marca

- La migración `0015_visual_identity_assets.sql` agrega revisiones append-only para dos alcances: empresa madre y marca de producto. Conserva nombre, cuatro colores, logo, SHA-256, operador, motivo y fecha.
- **Marcas** incluye un espacio para subir el logo y definir la paleta de Perfect Trading, además de controles equivalentes en cada tarjeta de marca. Las revisiones anteriores no se sobrescriben.
- La carga exige sesión, mismo origen, CSRF, confirmación y motivo; limita el logo a 5 MiB, acepta PNG/JPG/SVG y rechaza SVG con scripts, `foreignObject` o recursos externos.
- Los releases nuevos congelan las identidades madre y de producto. El empaquetador verifica ruta y SHA-256, incluye ambos logos en el bundle y los propaga a HTML, PDF, PPTX e InDesign según compatibilidad.
- Portada: Perfect Trading actúa como firma común y la marca de producto como marca de agua. Páginas interiores: la marca de producto mantiene el logo de esquina. SVG se conserva en HTML/InDesign; para presencia idéntica en PDF/PPTX se recomienda PNG/JPG.
- Operación: ejecutar una vez `ACTUALIZAR-SISTEMA.cmd`, entrar con `INICIAR-REVISOR.cmd`, abrir **Marcas**, guardar la identidad madre y después las marcas necesarias. Es obligatorio construir una versión nueva para incorporar los cambios.

## 2026-08-27 - Auditoría visual y accesibilidad 1.16

- La aplicación usa ahora una región `main` semántica real, avisos de resultado anunciables, blancos de confirmación de 24 px, foco visible en selectores visuales y respeto por `prefers-reduced-motion`.
- El HTML exportado incorpora un índice navegable por secciones, anclas estables y fichas semánticas `dl/dt/dd` para OEM, aplicaciones y motor. Las imágenes conservan `object-fit: contain` y carga diferida.
- El PDF incorpora metadatos de título, autor, asunto, creador, palabras clave y marcador de portada; conserva tipografía mínima de 12 pt, interlineado 1.8 y logos separados de empresa/marca.
- QA: HTML renderizado en Edge a 1440x1200 e inspeccionado sin recortes ni solapamientos. Edge headless no renderizó su visor PDF y Poppler no está instalado; la generación y estructura PDF sí quedaron cubiertas por pruebas automatizadas.
- Referencias aplicadas: WCAG 2.2 (foco, tamaño de objetivo, movimiento y estructura) y guías oficiales de Adobe sobre PDF etiquetado, orden de lectura, texto alternativo, metadatos, marcadores y compresión.
- Suite completa: 252 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

## 2026-08-27 - Corrección definitiva de encaje de imágenes 1.16.1

- La imagen del HTML digital y autónomo ocupa una caja explícita al 100% y usa `object-fit: contain` con centrado; el navegador ya no puede resolver `auto/max-height` de forma que termine ocultando extremos.
- Se reprodujo el caso con una imagen horizontal de 1600x900 marcada en sus cuatro bordes y se renderizó localmente en Edge. El original y la copia optimizada conservan su relación de aspecto y no se recortan.
- Los HTML ya exportados no se modifican retroactivamente: es necesario generar un entregable nuevo para recibir el CSS 1.16.1.
- Suite completa: 252 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

## 2026-08-31 - Paletas editables y fuentes oficiales de logos 1.39.1

- Una empresa o marca con identidad existente puede cambiar sus cuatro colores sin volver a cargar el logo. Se crea una revisión auditada nueva que reutiliza el hash, tipo y ruta del activo anterior; una identidad nueva todavía exige logo.
- `docs/FUENTES-OFICIALES-LOGOS-VEHICULARES.md` registra las fuentes corporativas verificadas para las 15 marcas reconocidas por el parser y advierte las restricciones de uso comercial/editorial.
- Se identificaron transiciones vigentes que requieren cuidado: Honda 2026, Mazda 2025 y Suzuki 2025 no deben sustituirse indiscriminadamente en modelos o mercados anteriores.
- No requiere migración de base de datos. Los colores se cambian en `INICIAR-REVISOR.cmd` → **Marcas** → **Identidad madre** después de seleccionar la empresa activa; hay que construir una edición nueva para propagarlos.

## 2026-08-31 - Registro vehicular global del parser v3

- El diccionario embebido se separó en `vehicle_makes.py`: 100 marcas normalizadas y 122 alias de turismos, SUV, pickups y camiones probables en América Latina, Norteamérica, Europa y Asia.
- Incluye equivalencias comerciales relevantes como Chirey→Chery, GWM→Great Wall, SsangYong→KGM, Chevy→Chevrolet y VW→Volkswagen.
- Se retiró la inferencia insegura GM→Chevrolet y no se aceptan como marca abreviaturas genéricas aisladas como RAM, MINI, SEAT o MAN.
- Las detecciones continúan siendo `pending_review`: no se publican ni aprueban automáticamente. Solo crean la marca al materializar una aplicación revisada.
- Los logos permanecen separados del parser. No se incorporan archivos de terceros o limitados a uso editorial; cada marca aprobada habilita su carga desde fuente oficial en **Marcas**.
- Referencias de cobertura: API vPIC de NHTSA y clasificación de fabricantes JRC/Comisión Europea. No requiere migración.
