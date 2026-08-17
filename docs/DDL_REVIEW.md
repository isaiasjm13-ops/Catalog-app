# Revisión del DDL PostgreSQL v0.2

> **DDL v0.2 aprobado después de la segunda revisión manual — pendiente de ejecución real en PostgreSQL**

Archivo revisado: `db/migrations/0001_initial_schema.sql`

Compatibilidad objetivo: PostgreSQL 16 o superior

Schema de aplicación: `perfect_catalog`

## 1. Resumen cuantitativo

| Elemento | Conteo | Criterio |
|---|---:|---|
| Tablas | 24 | Sentencias `CREATE TABLE perfect_catalog.*` |
| Primary keys | 24 | Una PK UUID por tabla |
| Foreign keys | 57 | Constraints `FOREIGN KEY` simples y compuestas |
| Checks | 171 | Constraints con prefijo `ck_` |
| Unique constraints | 21 | Constraints con prefijo `uq_`, sin contar PKs |
| Índices explícitos | 80 | Sentencias `CREATE INDEX` y `CREATE UNIQUE INDEX` |
| Índices únicos parciales | 13 | Subconjunto de los 80 índices explícitos |
| Índices automáticos esperados | 45 | 24 PKs + 21 unique constraints |
| Estructuras de índice esperadas | 125 | 80 explícitas + 45 automáticas, sujeto a verificación real |

PostgreSQL no crea automáticamente índices sobre las columnas que referencian una FK. Los
índices de acceso incluidos se eligieron por conciliación, estado, cronología y relaciones
operativas documentadas. No se incluyeron índices GIN sobre JSONB.

## 2. Matriz de las 24 tablas

| # | Tabla | Sección | PK | FKs principales | Restricciones críticas | Índices explícitos principales | Append-only por contrato | Decisión pendiente |
|---:|---|---|---|---|---|---|---|---|
| 1 | `source_system` | Integración | `source_system_id` | 0 | Código único; textos no vacíos; fechas coherentes | Activo | No | Zona horaria real de Odoo |
| 2 | `import_batch` | Integración | `import_batch_id` | 1: origen | Modo y estados permitidos; cierre posterior al inicio | Origen/fecha, estado | No; estados auditados | Autorización/transiciones en aplicación |
| 3 | `import_file` | Integración | `import_file_id` | 2: batch, duplicado | Hash hex; tamaño; mismo hash no es único; no autoenlace | Hash, batch/nombre, duplicado | Hash/tamaño/URI inmutables | Política futura de archivo |
| 4 | `staging_row` | Evidencia | `staging_row_id` | 1: archivo | Coordenada única; hash hex; sin `validation_status` | Hash | Sí | Archivado futuro preservando trazabilidad |
| 5 | `staging_row_result` | Procesamiento | `staging_row_result_id` | 2 compuestas: archivo/batch, fila/archivo | Versión/etapa/intento únicos; contexto coherente; hash; fechas | Fila/etapa/fecha, versiones, estado | Sí | Versiones reales de contrato y reglas |
| 6 | `import_issue` | Incidencias | `import_issue_id` | 4: batch y contextos compuestos | Severidad/estado; fila/resultado coherentes; resolución con evidencia | Batch/severidad/estado, fila, resultado, código | Evidencia original sí; resolución mutable | Autorización para aceptar/resolver |
| 7 | `import_plan` | Planes | `import_plan_id` | 3: batch, archivo contextual, plan anterior | Estados; tres hashes; actores/fechas; evidencia de aprobación/aplicación | Batch/fecha, archivo, estado, hash, predecesor | Contenido/hash sí; estado mutable | Transiciones y no reutilización operativa |
| 8 | `import_plan_item` | Planes | `import_plan_item_id` | 4: plan/archivo, fila/archivo, plantilla, variante | Orden único; objetivo generado; hash; decisión/actor | Fila, producto, operación, revisión | Sí; decisión crea plan sucesor | JSON canónico y hash en aplicación |
| 9 | `brand` | Catálogo | `brand_id` | 1: origen | Código único; ID fuente contextual parcial | ID fuente, nombre normalizado | No; cambios auditados | IDs estables reales de Odoo |
| 10 | `product_category` | Catálogo | `product_category_id` | 2: padre, origen | No puede ser su propio padre; ID fuente contextual | Padre, nombre, ID fuente | No; reparentado auditado | Ciclos de más de un nivel en aplicación |
| 11 | `product_template` | Catálogo | `product_template_id` | 5: origen, marca, categoría, fila, batch | IDs no vacíos; claves contextuales; status seguro | Odoo/external parciales, marca, categoría, status, nombre, batch | No; cambios auditados | IDs Odoo y zona fuente reales |
| 12 | `product_variant` | Catálogo | `product_variant_id` | 2: plantilla/origen, fila | ID realmente no vacío; mismo origen de plantilla; status seguro | Odoo/external parciales, status | No; cambios auditados | Exportación real de variantes |
| 13 | `product_reference` | Catálogo | `product_reference_id` | 3: contexto de producto, variante, fila | Origen/marca coherentes; revisión con evidencia; sin unique global | Conciliación contextual, producto/tipo, revisión | Original sí; revisión auditada | Resolución humana de duplicados |
| 14 | `inventory_snapshot` | Inventario | `inventory_snapshot_id` | 3 compuestas: plan, fila, item exacto | Cantidades con signo; un snapshot por item; objetivo exacto | Producto/fecha, variante/fecha, batch, plan, archivo/fila | Sí | Compactación futura según volumen |
| 15 | `media_asset` | Medios | `media_asset_id` | 2: origen, fila | Estados; hash/tamaño; campos exigidos al procesar | Hash único parcial, estado, fila | Evidencia de origen sí; procesamiento auditado | Directorio y backend inicial concretos |
| 16 | `product_media` | Medios | `product_media_id` | 3: plantilla, variante, medio | `is_primary` no nulo; asociaciones/primarios únicos parciales | Medio; asociaciones y primarios parciales | No; cambios auditados | Reglas futuras de roles |
| 17 | `vehicle_make` | Vehículos | `vehicle_make_id` | 0 | ID opcional no vacío; revisión con evidencia | Nombre aprobado, estado de revisión | Evidencia/revisión auditadas | Reglas empresariales de aplicaciones |
| 18 | `vehicle_model` | Vehículos | `vehicle_model_id` | 1: marca vehicular | Clave contextual; revisión con evidencia | Nombre aprobado, revisión | Evidencia/revisión auditadas | Vocabulario empresarial validado |
| 19 | `vehicle_engine` | Vehículos | `vehicle_engine_id` | 2: marca, modelo contextual | Puede ser general; revisión con evidencia | Modelo, código, nombre, revisión | Evidencia/revisión auditadas | Normalización empresarial de motores |
| 20 | `product_application_candidate` | Candidatos | `product_application_candidate_id` | 6: producto, fila y contexto vehicular | Marca/modelo/motor coherentes; revisión con evidencia | Producto, revisión, vehículo, años | Evidencia/regla sí; revisión auditada | Reglas vehiculares específicas |
| 21 | `extraction_candidate` | Candidatos | `extraction_candidate_id` | 2: fila, producto | Normalizado no vacío; revisión con evidencia | Tipo/revisión, fila, producto | Evidencia/regla sí; revisión auditada | Calibración de reglas y umbrales |
| 22 | `catalog_release` | Publicación | `catalog_release_id` | 1: marca | Publicar/archivar exige hash, actor y fechas coherentes | Marca/status, publicación, hash | Definición sí; estado auditado | Autorización y cálculo canónico global |
| 23 | `catalog_release_item` | Publicación | `catalog_release_item_id` | 4: release/marca, plantilla/marca, variante, batch | No mezcla marcas; snapshot/version/hash obligatorios | Producto, sección, hash | Sí | Serialización JSON canónica |
| 24 | `audit_event` | Auditoría | `audit_event_id` | 3: batch, plan, fila | Hash; actor/evento/entidad; motivo para actor humano | Entidad/fecha, batch, plan, correlación, evento | Sí | Retención legal y control de escritura |

## 3. Mapeo entre diseño y DDL

| Decisión de `DATABASE_DESIGN.md` | Implementación en el DDL |
|---|---|
| UUID interno estable | Las 24 PK son `uuid` sin generador ni dependencia externa |
| IDs Odoo contextuales | Columnas nullable e índices únicos parciales por `source_system_id` |
| Nombre no identifica | Ningún `name` de producto tiene unique |
| Referencias duplicadas permitidas | Índice no único `(source_system_id, brand_id, value_normalized)` |
| `source_active` desconocido | `source_active boolean` nullable en plantilla y variante |
| Estado interno separado | `catalog_status` con default `pending_review` y CHECK de cuatro estados |
| Staging inmutable | `staging_row` contiene solo evidencia; resultados en `staging_row_result` |
| Plan exacto | Archivo/contrato/reglas/hash/fingerprint en `import_plan`; items hasheados |
| Aplicación única | Estado `approved/applying/applied`, fechas y fingerprint; transición final queda en aplicación |
| Variante coherente | FKs compuestas `(product_template_id, product_variant_id)` donde corresponde |
| Inventario histórico | Snapshot enlazado al batch, plan, archivo, fila e item exactos; unique por item aplicado |
| Medios fuera del producto | `media_asset` conserva backend/URI/hash/tipo/tamaño/estado; producto solo relaciona |
| Candidatos vehiculares | Confidence, estado de revisión, evidencia y reglas versionadas |
| Releases reproducibles | Definición, items JSON versionados y hashes; estados controlados |
| Auditoría append-only | Evento con actor, entidad, before/after, razón, hash y contexto opcional |
| Sin borrado automático | Todas las FKs usan `ON DELETE RESTRICT` |

## 4. Correcciones posteriores a la primera revisión manual

| Problema detectado | Garantía agregada | Tablas afectadas | Todavía depende de la aplicación |
|---|---|---|---|
| IDs opcionales aceptaban espacios | CHECK no vacío e índices parciales que excluyen `NULL` y blanco | `source_system`, `brand`, `product_category`, productos y vocabulario vehicular | Formato y validez empresarial del ID |
| Variante podía declarar otro origen | FK compuesta plantilla/origen | `product_template`, `product_variant` | Conciliación contra IDs reales de Odoo |
| Referencia podía mezclar producto, origen o marca | FK compuesta al contexto de plantilla; variante coherente | `product_template`, `product_reference` | Resolver duplicados y elegir matches; no hay unique global |
| Resultado/item podía usar evidencia de otro archivo | `import_file_id` contextual y FKs compuestas | `staging_row`, `staging_row_result`, `import_plan`, `import_plan_item` | Construcción y serialización del plan |
| Snapshot podía mezclar batch, plan, archivo, fila o producto | FK al plan contextual y al item exacto; objetivo generado; unique por item | `inventory_snapshot`, `import_plan_item` | Append-only mediante permisos y cálculo de cantidades |
| Incidencia podía mezclar archivo/fila/resultado | FKs compuestas a fila y resultado con batch/archivo | `import_issue`, `staging_row_result` | Autorización para resolver/aceptar |
| Item de release podía mezclar marcas | `brand_id` contextual y dos FKs compuestas | `catalog_release`, `catalog_release_item`, `product_template` | Completitud y JSON canónico del release |
| Candidatos vehiculares podían combinar jerarquías incompatibles | Claves make/model/engine y FKs compuestas cuando los IDs están presentes | `vehicle_model`, `vehicle_engine`, `product_application_candidate` | Resolver candidatos generales o ambiguos |
| Estados revisados no exigían evidencia suficiente | Actor no vacío, fecha y coherencia temporal para `approved/rejected` | Referencias, candidatos, make/model/engine | Autorización e identidad real del actor; auditoría del cambio |
| Resolución/publicación admitía estados incompletos | Evidencia obligatoria; un release solo se archiva con publicación previa | `import_issue`, `catalog_release` | Historial de transición y separación de funciones |
| Banderas/valores permitían ambigüedad evitable | `is_primary NOT NULL DEFAULT false`; normalizado de extracción no vacío | `product_media`, `extraction_candidate` | Significado empresarial de roles y normalización |

Las claves alternativas que comienzan por una PK son deliberadamente redundantes desde el punto
de vista de identidad: existen únicamente porque PostgreSQL exige una clave unique exacta como
destino de una FK compuesta. No autorizan conciliación ni fusión automática.

## 5. Revisión de índices después de las claves contextuales

Se retiraron cuatro índices explícitos cuya columna inicial quedó completamente cubierta por una
PK/unique no parcial usada por las mismas búsquedas y FKs:

- `ix_staging_row_result_batch`: cubierto por `uq_staging_row_result_context`, cuyo prefijo es `import_batch_id`.
- `ix_import_plan_item_plan`: cubierto por `uq_import_plan_item_order`, cuyo prefijo es `import_plan_id`.
- `ix_product_variant_template`: cubierto por `uq_product_variant_template_variant`, cuyo prefijo es `product_template_id`.
- `ix_vehicle_model_make`: cubierto por `uq_vehicle_model_make_model`, cuyo prefijo es `vehicle_make_id`.

Se agregó `ix_inventory_snapshot_file_row` para trazabilidad y comprobaciones por archivo/fila. Se
conservaron índices que pueden parecer cercanos a una clave, pero responden a otro prefijo o filtro:

- `ix_import_file_batch_name`, porque la unique contextual termina en ID y no resuelve búsqueda por nombre.
- `ix_product_template_source_brand`, porque las claves alternativas comienzan por `product_template_id`.
- `ix_inventory_snapshot_plan`, porque las claves contextuales comienzan por batch o item y no por plan.
- `ix_catalog_release_brand_status`, porque la unique de versión no filtra estado dentro de marca.
- `ix_product_reference_reconciliation`, porque es búsqueda contextual deliberadamente no unique.
- `ix_product_application_vehicle`, porque acelera validación/consulta del triple candidato en la tabla hija.

El total explícito baja de 83 a 80 por cuatro retiros y una adición justificada. La utilidad real
de los restantes todavía debe medirse con consultas y volumen en PostgreSQL.

## 6. Garantías que requieren aplicación

El DDL reduce estados inválidos, pero no puede garantizar por sí solo:

- el orden histórico de todas las transiciones de `import_batch`, `import_plan` y releases;
- autorización, separación de funciones y aprobación humana real;
- impedir todo `UPDATE`/`DELETE` sobre tablas append-only sin un modelo de roles/permisos;
- que un plan aplicado no sea manipulado para aparentar un estado anterior;
- serialización JSON canónica y orden determinista de propiedades;
- cálculo correcto de SHA-256 y del fingerprint de aprobación;
- que `file_sha256` corresponda físicamente al archivo indicado por `storage_uri`;
- reglas de conciliación y resolución humana de referencias duplicadas;
- extracción, confianza y reglas empresariales vehiculares;
- almacenamiento físico, respaldo y migración de imágenes;
- ausencia de ciclos de categoría de longitud mayor que uno;
- que una publicación contenga todos sus items antes de pasar a `published`;
- inmutabilidad operacional y retención, que requieren roles, servicios y auditoría;
- integridad polimórfica de `audit_event.entity_id`.

### Decisión sobre `audit_event.entity_id`

`entity_id` no tiene FK porque una sola columna puede referirse a múltiples tablas y PostgreSQL no
ofrece una FK polimórfica real. Crear una FK falsa o incompleta daría una garantía engañosa. La
aplicación debe validar `entity_type + entity_id`; las FKs concretas de batch, plan y staging sí
están implementadas.

### Seguimiento para la capa de aplicación

La segunda revisión manual aprueba el DDL v0.2 sin trasladar al motor garantías que requieren
contexto, identidad o una secuencia histórica. El importador y los servicios deberán garantizar:

- transiciones válidas de estados;
- autorización y separación de funciones;
- valores permitidos para decisiones humanas;
- coherencia temporal de `decided_at`;
- que un plan sucesor pertenezca al mismo contexto empresarial;
- candidatos vehiculares parciales que no puedan resolverse solamente mediante FKs;
- coincidencia entre el origen declarado del producto y su evidencia de creación;
- cálculo y verificación de hashes;
- JSON canónico;
- inmutabilidad mediante permisos y servicios;
- ciclos de categorías de más de un nivel.

Estas observaciones no bloquean la validación sintáctica del DDL, pero deben conservarse para la
implementación.

## 7. Riesgos y limitaciones

- El DDL aún no ha sido interpretado por un servidor PostgreSQL real.
- Los 80 índices explícitos deben revisarse con consultas y volumen reales; algunos podrían ser
  redundantes o costosos en escritura.
- Los JSONB no tienen validación de esquema interna; su contrato vive versionado fuera del motor.
- Un CHECK no impide que un actor con permisos amplios edite evidencia histórica.
- La jerarquía de categorías solo impide auto-parentesco directo; ciclos largos requieren lógica adicional.
- La unicidad parcial de vocabularios vehiculares depende de marcar correctamente `review_status`.
- La zona de Odoo y el sistema 1900/1904 siguen sin confirmarse; los timestamps normalizados no
  deben poblarse definitivamente hasta resolverlos.
- La política futura de archivo y la ubicación inicial de imágenes siguen abiertas.
- Las columnas contextuales y generadas aumentan el costo de escritura; su beneficio debe validarse
  con planes de consulta y pruebas sintéticas en PostgreSQL 16+.

## 8. Checklist manual previo a cualquier ejecución

La instalación y la creación de `perfect_catalog_dev` son pasos externos a este DDL. La versión
mayor aprobada es PostgreSQL 18 x64; la minor debe reconfirmarse en PostgreSQL.org justo antes de
descargar. La base futura deberá crearse desde `template0`, con UTF8, proveedor ICU, locale `es-PA`
y collation predeterminada determinista. El instalador gráfico puede usar un locale de Windows para
el clúster, pero `Spanish_Panama.1252` no será la collation definitiva de la base del proyecto.

- [ ] Confirmar en PostgreSQL.org la minor estable vigente de PostgreSQL 18 x64.
- [ ] Verificar URL oficial PostgreSQL → EDB, publicador, firma digital y SHA-256 del instalador.
- [ ] Presentar esa evidencia y obtener autorización humana antes de ejecutar el instalador.
- [ ] Confirmar `perfect_catalog_dev`: UTF8, proveedor ICU, locale `es-PA` y collation determinista.
- [ ] Confirmar checksums de datos habilitados y zona horaria del servidor en UTC.
- [x] Verificar hash y segunda revisión manual aprobada de la migración.
- [ ] Confirmar que la base de destino esté vacía y sea la correcta.
- [ ] Confirmar respaldo y restauración cuando aplique.
- [ ] Revisar las 24 tablas y que no exista ninguna adicional.
- [ ] Revisar las 57 FKs y sus acciones restrictivas.
- [ ] Revisar 171 checks, 21 unique constraints y 80 índices explícitos.
- [ ] Confirmar que no hay extensiones, credenciales ni datos empresariales.
- [ ] Confirmar que no existen operaciones destructivas en el archivo.
- [ ] Revisar locks y costo estimado de índices.
- [ ] Ejecutar primero en local/prueba, nunca directamente en producción.
- [ ] Verificar catálogo real de PostgreSQL después de ejecutar.
- [ ] Probar inserts sintéticos válidos e inválidos.
- [ ] Probar rollback completo de la transacción.
- [ ] Documentar duración, resultados y cualquier compensación necesaria.

Las pruebas estáticas de `tests/test_schema_contract.py` complementan este checklist, pero no
reemplazan la futura ejecución real en PostgreSQL.
