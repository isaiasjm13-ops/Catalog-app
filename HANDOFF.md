# HANDOFF.md - Estado de Traspasos Entre Sesiones

## Sesión actual: Estudio visual de catálogos (2026-08-26)

### Resultado de esta sesión

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
- Suite local actual: 197 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

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
- API FastAPI v1.1 de solo lectura implementada sin retirar el visor existente.
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
