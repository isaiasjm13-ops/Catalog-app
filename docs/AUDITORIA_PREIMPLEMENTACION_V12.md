# Auditoría preimplementación - Especificación multiempresa v12

Fecha: 2026-08-31  
Base auditada: commit `ad738ab`  
Documento de referencia: `Especificacion_Catalogo_Multiempresa_Django_v12.pdf` (42 páginas)

## 1. Dictamen ejecutivo

El proyecto real no es Django. Es una aplicación local FastAPI + Jinja2 + PostgreSQL con un único
motor de importación, revisión, publicación y exportación. Migrar a Django o crear una aplicación
paralela queda **rechazado**: no aporta valor funcional, duplicaría la fuente de verdad y pondría en
riesgo los flujos ya verificados.

La arquitectura actual es una base favorable para extender los objetivos del documento, pero **no
es todavía multiempresa**. Existe `brand`, un perfil visual por marca y una identidad visual con
scope textual `company`; esta última representa hoy una identidad corporativa global, no una
entidad Company aislada. No existe `corporation`, `company`, contexto de compañía activa,
autorización por compañía ni FK Company en marcas/productos/categorías/releases.

La recomendación es una migración gradual dentro del esquema y servicios actuales:

1. formalizar Company y el historial de migraciones;
2. asignar los datos actuales con mapping explícito y backup;
3. introducir contexto de Company y aislamiento autoritativo;
4. extender la importación y referencias cruzadas;
5. estabilizar y probar el HTML autónomo en móvil;
6. agregar scopes Company/corporate sobre el mismo motor;
7. llevar la misma resolución visual a todos los formatos.

No se autoriza todavía ninguna migración estructural. Falta inspeccionar la base PostgreSQL real,
contar/identificar registros y aprobar el mapping Company/Brand con el usuario.

## 2. Evidencia y salud actual

- Stack: `pyproject.toml`, `src/perfect_catalog/operator_api.py`, `src/perfect_catalog/api.py`.
  FastAPI/Jinja2/PostgreSQL; no hay Django ni ORM.
- Base maestra: `db/migrations/0001_initial_schema.sql` contiene marcas, categorías, productos,
  variantes, referencias, aplicaciones, medios, releases y auditoría.
- Importación segura: `src/perfect_catalog/importer.py`, `intake.py`, `intake_promotion.py` y tablas
  `staging_row`, `import_plan`, `import_plan_item`. Ya hay dry-run, hash, revisión y aplicación.
- Publicación reproducible: `publication.py`, `releases.py` y `catalog_release*` usan snapshots y
  SHA-256 inmutables.
- Exportador único: `catalog_exports.py` y `catalog_export_job.py` generan HTML, HTML autónomo,
  PDF, PPTX e InDesign desde el release verificado.
- Identidad visual: `brand_profiles.py`, `visual_identities.py`, migraciones 0013-0016. Es parcial:
  marca, identidad corporativa global y logo vehicular, pero sin Company persistida.
- Consola: sesión temporal local, cookie HttpOnly, CSRF, mismo origen, TrustedHost, CSP y límites
  de intentos en `operator_api.py`.
- Verificación 2026-08-31: 260 pruebas pasan; 6 pruebas PostgreSQL se omiten sin credenciales.
  `compileall` y los tres JavaScript estáticos pasan. No se realizó prueba contra la BD real.
- Árbol de trabajo previo: `CONTINUAR-PROYECTO-CATALOGO.md` y `data/brand-assets/` no rastreados;
  se preservaron por pertenecer al usuario.

## 3. Mapa de arquitectura reutilizable

| Área | Fuente actual | Decisión |
|---|---|---|
| Datos maestros | `0001_initial_schema.sql` | Extender conservadoramente |
| Ingreso/Excel | `intake.py`, `importer.py`, `intake_promotion.py` | Reutilizar y extender |
| Reconciliación | `import_plan*`, revisiones y apply transaccional | Reutilizar |
| Referencias | `product_reference` | Reutilizar para A1; no crear tabla duplicada |
| Aplicaciones | `vehicle_*`, `product_application_candidate` | Reutilizar |
| Publicación | `catalog_release*`, snapshots, hashes | Reutilizar |
| Exportación | `catalog_exports.py`, `catalog_export_job.py` | Un solo motor; extender |
| HTML móvil | `generate_catalog_html()` y visor `dialog` | Extender y validar en dispositivos |
| Identidad | `brand_profile`, `visual_identity_revision` | Migrar scope corporativo a Company real |
| Operador | FastAPI/Jinja2/JS/CSS | Extender; no reemplazar por Django |
| Seguridad | autenticación local + CSRF/origen/CSP | Conservar; añadir permisos Company |

## 4. Matriz de decisión y favorabilidad

| Requisito | Estado | Beneficio | Riesgo / complejidad | Decisión | Acción mínima |
|---|---|---:|---:|---|---|
| Migrar a Django | Desaconsejado | Bajo | Alto / alta | Rechazar | Mantener FastAPI y cumplir los objetivos |
| Corporation | No existe | Bajo inicial | Medio / media | Posponer | Añadir sólo si se confirma jerarquía superior real |
| Company | No existe | Alto | Alto / alta | Aprobar con condiciones | Tabla Company + backfill verificado y reversible |
| Brand pertenece a Company | No existe | Alto | Alto / media | Aprobar con condiciones | FK nullable, mapping, validación, después NOT NULL |
| Category/Product con Company directa | No existe | Alto | Alto / alta | Aprobar con condiciones | Evaluar derivación por Brand antes de duplicar FK |
| Company activa | No existe | Alto | Alto / media | Aprobar tras modelo | Sesión + servicio de contexto, no middleware Django |
| Usuarios/permisos por Company | No existe | Alto si hay varios operadores | Alto / alta | Posponer hasta definir usuarios | Mantener operador local; diseñar ACL antes de exponer red |
| CompanySettings | Parcial (`localStorage` y config por export) | Medio | Medio / media | Aprobar después de Company | Persistir sólo defaults útiles; no JSON sin contrato ilimitado |
| Identidad Company + Brand | Parcial | Alto | Alto / media | Aprobar con condiciones | Asociar revisión company a Company; resolver tema una vez |
| Catálogo por Brand | Ya existe | Alto | Bajo | Reutilizar | Release actual por `brand_id` |
| Catálogo custom | Parcial | Alto | Bajo / baja | Extender | Filtros/selección ya existen; persistir definición reusable |
| Catálogo general Company | No existe | Alto | Medio / media | Aprobar tras aislamiento | Selección multibrand en el motor actual |
| Catálogo corporate | No existe | Medio | Alto / alta | Posponer | Sólo tras Company y catálogo general estables |
| Excel con preview/aprobación | Ya existe | Alto | Bajo | Reutilizar | Añadir contexto Company/Brand y diffs de campo faltantes |
| Vacíos no borran datos | Parcial / requiere prueba real | Alto | Medio / media | Aprobar con condiciones | Pruebas create/update/no_change/conflict y política explícita |
| Base maestra separada de catálogo | Ya existe | Alto | Bajo | Reutilizar | Productos + releases inmutables |
| Catálogos desactualizados | No existe | Alto | Medio / media | Aprobar después de scopes | Comparar reglas/snapshot con base actual; no editar HTML |
| A1 cross references | Parcial | Alto | Medio / media | Aprobar con condiciones | Extender `product_reference`; deduplicar y buscar sin fabricante |
| Fabricante de cross reference | Desaconsejado | Bajo | Alto / alta | Rechazar | Guardar únicamente códigos y metadatos de calidad |
| HTML autónomo único/offline | Ya existe | Alto | Bajo | Reutilizar | No crear V2 separado; evolucionar el generador actual |
| Visor táctil/ficha | Parcialmente probado | Alto | Medio / baja | Aprobar | Prueba real Edge/Chrome/Android/iPhone; corregir el visor existente |
| Búsqueda multipalabra/códigos | Parcial | Alto | Medio / baja | Aprobar | Índice explícito, tokens y normalización de espacios/guiones |
| Filtros móviles avanzados | Parcial | Medio | Medio / media | Aprobar por etapas | Medir DOM/peso antes de agregar controles |
| Favoritos/modo oscuro/historial | No existe | Bajo | Bajo-medio | Posponer | No desplazar aislamiento, importación y móvil |
| Paridad HTML/PDF/InDesign | Parcial | Alto | Medio / media | Aprobar después de resolver tema | Un `ResolvedVisualProfile` congelado por release |

## 5. Hallazgos técnicos priorizados

### Críticos antes de multiempresa

1. **No hay aislamiento Company.** `brand.code` es único globalmente y `catalog_release` sólo tiene
   `brand_id`. Agregar Company sin mapping previo puede reasignar o mezclar datos.
2. **El scope `company` actual es global.** `publication._resolve_plan_brand()` toma la revisión
   corporativa más reciente sin Company ID. Con varias empresas esto produciría fuga de identidad.
3. **No hay ledger formal de migraciones.** `apply_pending_migrations.sql` infiere estado por tablas
   y columnas. Funcionó para 0007-0016, pero una migración multiempresa necesita historial, versión,
   checksum y verificación previa/posterior para evitar los fallos manuales ya observados.
4. **La BD real no fue inspeccionada.** Las seis pruebas de integración se omiten sin contraseña.
   Estado del esquema, permisos, cardinalidades y calidad de datos: evidencia insuficiente.

### Altos

5. **A1 puede reutilizar `product_reference`.** Ya conserva original/normalizada, tipo, producto,
   estado y nota. Faltan contrato de tipos A1, unicidad lógica por producto+normalizada, detección de
   conflicto entre productos, importación multicolumna y exposición completa en snapshots/HTML.
6. **La búsqueda HTML no es realmente multipalabra.** Usa `card.dataset.search.includes(term)`;
   exige una subcadena contigua. Tampoco genera una clave de código sin espacios/guiones. Debe
   indexar tokens y referencias aunque un campo no se muestre visualmente.
7. **Validación móvil pendiente.** El visor usa `dialog`, touch por `click`, `contain` y ficha clonada,
   pero no existe evidencia manual en Android/iPhone ni pruebas de viewport/scroll/foco.
8. **El HTML autónomo incorpora todas las imágenes Base64.** Hay optimización raster y `loading=lazy`,
   pero el payload completo permanece dentro del archivo. Se necesita benchmark con 500, 5.000 y
   25.000 productos y límites/segmentación de catálogo, sin romper el modo offline.

### Medios

9. `operator_api.py` concentra muchas rutas y capturas genéricas. No se encontró exposición directa
   de secretos y usa diagnósticos seguros, pero conviene separar servicios/rutas antes de añadir
   contexto y permisos multiempresa.
10. `ImportPerfectCatalog.jsx` usa `eval` únicamente tras validar gramática JSON para compatibilidad
    con ExtendScript antiguo. Es riesgo contenido, no prioritario; mantener snapshots locales y no
    aceptar JSON no confiable.
11. `data/brand-assets/` no está cubierto por `.gitignore` y aparece sin seguimiento. Definir si son
    datos operativos respaldados fuera de Git o fixtures aprobados; no agregarlos automáticamente.
12. Documentación y mensajes muestran mojibake al usar `Get-Content` predeterminado en PowerShell.
    Los archivos deben verificarse por bytes/UTF-8 antes de concluir que están dañados; normalizar
    la lectura de scripts a `-Encoding utf8`.

## 6. Plan por fases, pruebas y rollback

### Fase 0 - evidencia de base y migraciones

- Backup lógico verificable de `perfect_catalog_dev`.
- Inspeccionar versión real, permisos, filas por marca/categoría/producto/release e identidades.
- Crear propuesta de ledger de migraciones con checksum; no ejecutar aún.
- Acordar mapping inicial: Perfect Company->Perfect; KMC->A1; Natsuki->Natsuki; Masaki->Masaki;
  PDM->lista OEM confirmada.
- Rollback: ninguno porque es sólo lectura/documentación.

### Fase 1 - Company y pertenencia de Brand

- Migración forward-only: Company, FK Brand nullable, restricciones diferidas y data migration
  separada. No introducir Company directa en todas las tablas sin demostrar necesidad.
- Pruebas: pertenencia, rechazo cruzado, duplicados de código por ámbito decidido, backfill exacto,
  permisos SQL y reejecución segura.
- Rollback: restaurar backup o retirar feature flag antes de volver FK obligatoria.

### Fase 2 - contexto y aislamiento

- Servicio `CompanyContext` para FastAPI, selector visible y filtros autoritativos en gateway.
- Mantener modo de una sola Company hasta completar pruebas de aislamiento.
- Pruebas negativas: IDs manuales, cambio de sesión, descargas, logos, releases y exportaciones.
- Rollback: feature flag vuelve a Company predeterminada sin borrar relaciones.

### Fase 3 - importación y A1

- Company antes de Brand; Brand filtrada y validada por backend.
- Extender `product_reference`, no crear `ProductCrossReference` paralelo.
- Preview de nuevas/existentes/conflictos; vacíos conservan datos; idempotencia del mismo Excel.
- Rollback: planes no aplicados se descartan; apply sigue transaccional y auditable.

### Fase 4 - HTML autónomo estable

- Búsqueda por tokens y códigos normalizados, resumen de referencias y lista expandida.
- Pruebas manuales y automatizadas móvil; benchmark de tamaño/memoria/tiempo.
- Límites de producto/imagen explícitos y recomendación de dividir catálogos grandes.
- Rollback: conservar generador anterior bajo versión de contrato durante una transición corta.

### Fase 5 - catálogos Company y actualización

- Persistir definición reproducible; multibrand sobre `_selection/_groups` existentes.
- Detectar cambios comparando definición + snapshot actual; regenerar, nunca editar HTML distribuido.
- Corporate se evalúa sólo después de aceptar esta fase.

### Fase 6 - paridad de formatos

- Resolver una identidad Company/Brand por request y congelarla en el release.
- HTML, PDF, PPTX e InDesign consumen el mismo snapshot con adaptación de layout por formato.
- Validación visual y preflight por formato.

## 7. Propuestas rechazadas o pospuestas

- Rechazado: migrar el proyecto a Django.
- Rechazado: una base física o copia de aplicación por Company.
- Rechazado: segunda tabla/motor de referencias si `product_reference` puede extenderse.
- Rechazado: inferir o mostrar fabricante de equivalencias A1.
- Rechazado: un segundo exportador “HTML autónomo V2”.
- Pospuesto: Corporation hasta confirmar necesidad funcional.
- Pospuesto: usuarios/roles complejos hasta definir operación multiusuario o exposición en red.
- Pospuesto: corporate, favoritos, modo oscuro e historial local hasta estabilizar aislamiento,
  importación y HTML móvil.
- Pospuesto: nuevas mejoras InDesign/PDF que no sean regresiones, siguiendo la prioridad del PDF.

## 8. Puerta para comenzar implementación

Antes de editar estructura deben cumplirse estas condiciones:

- [ ] Backup PostgreSQL creado y restauración probada.
- [ ] Esquema real 0001-0016 y permisos inspeccionados.
- [ ] Mapping Company/Brand inicial aprobado, incluida lista PDM OEM.
- [ ] Decisión sobre unicidad de `brand.code` global o por Company.
- [ ] Decisión sobre Company derivada por Brand frente a FK directa en Product/Category.
- [ ] Estrategia de migraciones con ledger/checksum aprobada.
- [ ] Feature flag/Company predeterminada definida para compatibilidad gradual.
- [ ] Casos de aislamiento y rollback escritos antes de ejecutar SQL.

Hasta entonces el estado es: **auditoría completa de código y especificación; implementación
estructural bloqueada correctamente por evidencia insuficiente de la base real y decisiones de
mapping**.
