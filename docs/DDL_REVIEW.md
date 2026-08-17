# Revisión del DDL PostgreSQL v0.1

> **Borrador revisable — No ejecutado — Ninguna tabla real creada**

Archivo revisado: `db/migrations/0001_initial_schema.sql`

Compatibilidad objetivo: PostgreSQL 16 o superior

Schema de aplicación: `perfect_catalog`

## 1. Resumen cuantitativo

| Elemento | Conteo | Criterio |
|---|---:|---|
| Tablas | 24 | Sentencias `CREATE TABLE perfect_catalog.*` |
| Primary keys | 24 | Una PK UUID por tabla |
| Foreign keys | 60 | Constraints `FOREIGN KEY` |
| Checks | 137 | Constraints con prefijo `ck_` |
| Unique constraints | 11 | Constraints con prefijo `uq_`, sin contar PKs |
| Índices explícitos | 83 | Sentencias `CREATE INDEX` y `CREATE UNIQUE INDEX` |
| Índices únicos parciales | 13 | Subconjunto de los 83 índices explícitos |
| Índices automáticos esperados | 35 | 24 PKs + 11 unique constraints |
| Estructuras de índice esperadas | 118 | 83 explícitas + 35 automáticas, sujeto a verificación real |

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
| 5 | `staging_row_result` | Procesamiento | `staging_row_result_id` | 2: fila, batch | Versión/etapa/intento únicos; hash; fechas | Fila/etapa/fecha, batch, versiones, estado | Sí | Versiones reales de contrato y reglas |
| 6 | `import_issue` | Incidencias | `import_issue_id` | 4: batch, archivo, fila, resultado | Severidad/estado; pareja de resolución | Batch/severidad/estado, fila, resultado, código | Evidencia original sí; resolución mutable | Autorización para aceptar/resolver |
| 7 | `import_plan` | Planes | `import_plan_id` | 3: batch, archivo contextual, plan anterior | Estados; tres hashes; actores/fechas; evidencia de aprobación/aplicación | Batch/fecha, archivo, estado, hash, predecesor | Contenido/hash sí; estado mutable | Transiciones y no reutilización operativa |
| 8 | `import_plan_item` | Planes | `import_plan_item_id` | 4: plan, fila, plantilla, variante coherente | Orden único; operación; hash; decisión/actor | Plan, fila, producto, operación, revisión | Sí; decisión crea plan sucesor | JSON canónico y hash en aplicación |
| 9 | `brand` | Catálogo | `brand_id` | 1: origen | Código único; ID fuente contextual parcial | ID fuente, nombre normalizado | No; cambios auditados | IDs estables reales de Odoo |
| 10 | `product_category` | Catálogo | `product_category_id` | 2: padre, origen | No puede ser su propio padre; ID fuente contextual | Padre, nombre, ID fuente | No; reparentado auditado | Ciclos de más de un nivel en aplicación |
| 11 | `product_template` | Catálogo | `product_template_id` | 5: origen, marca, categoría, fila, batch | `source_active` nullable; status seguro; contador no negativo; IDs contextuales | Odoo/external parciales, marca, categoría, status, nombre, batch | No; cambios auditados | IDs Odoo y zona fuente reales |
| 12 | `product_variant` | Catálogo | `product_variant_id` | 3: plantilla, origen, fila | Identificador real requerido; status seguro; clave compuesta de coherencia | Odoo/external parciales, plantilla, status | No; cambios auditados | Exportación real de variantes |
| 13 | `product_reference` | Catálogo | `product_reference_id` | 5: origen, marca, plantilla, variante, fila | Original/normalizado texto; confidence 0..1; sin unique global | Conciliación contextual, producto/tipo, revisión | Original sí; revisión/normalización auditadas | Resolución humana de duplicados |
| 14 | `inventory_snapshot` | Inventario | `inventory_snapshot_id` | 5: plantilla, variante, batch, plan, fila | Cantidades sin límite de signo; unique lógico con NULL no distinto | Producto/fecha, variante/fecha, batch, plan | Sí | Compactación futura según volumen |
| 15 | `media_asset` | Medios | `media_asset_id` | 2: origen, fila | Estados; hash/tamaño; campos exigidos al procesar | Hash único parcial, estado, fila | Evidencia de origen sí; procesamiento auditado | Directorio y backend inicial concretos |
| 16 | `product_media` | Medios | `product_media_id` | 3: plantilla, variante, medio | Variante coherente; orden; asociaciones/primarios únicos por índices parciales | Medio; asociaciones y primarios parciales | No; cambios auditados | Reglas futuras de roles |
| 17 | `vehicle_make` | Vehículos | `vehicle_make_id` | 0 | Revisión; nombre aprobado único parcial | Nombre aprobado, estado de revisión | Evidencia/revisión auditadas | Reglas empresariales de aplicaciones |
| 18 | `vehicle_model` | Vehículos | `vehicle_model_id` | 1: marca vehicular | Revisión; nombre aprobado único dentro de marca | Marca, nombre aprobado, revisión | Evidencia/revisión auditadas | Vocabulario empresarial validado |
| 19 | `vehicle_engine` | Vehículos | `vehicle_engine_id` | 1: modelo | Revisión; cilindrada/cilindros positivos si existen | Modelo, código, nombre, revisión | Evidencia/revisión auditadas | Normalización empresarial de motores |
| 20 | `product_application_candidate` | Candidatos | `product_application_candidate_id` | 5: producto, fila, marca, modelo, motor | Confidence; revisión; años positivos/coherentes; actor | Producto, revisión, vehículo, años | Evidencia/regla sí; revisión auditada | Reglas vehiculares específicas |
| 21 | `extraction_candidate` | Candidatos | `extraction_candidate_id` | 2: fila, producto | Confidence; revisión; regla/evidencia no vacías | Tipo/revisión, fila, producto | Evidencia/regla sí; revisión auditada | Calibración de reglas y umbrales |
| 22 | `catalog_release` | Publicación | `catalog_release_id` | 1: marca | Versión única por marca; estados; publicación exige hash/actor | Marca/status, publicación, hash | Definición sí; estado auditado | Autorización y cálculo canónico global |
| 23 | `catalog_release_item` | Publicación | `catalog_release_item_id` | 4: release, plantilla, variante, batch | Orden único; snapshot/version/hash obligatorios | Producto, sección, hash | Sí | Serialización JSON canónica |
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
| Inventario histórico | Snapshot enlazado a batch, plan, fila y producto; unique lógico de reintento |
| Medios fuera del producto | `media_asset` conserva backend/URI/hash/tipo/tamaño/estado; producto solo relaciona |
| Candidatos vehiculares | Confidence, estado de revisión, evidencia y reglas versionadas |
| Releases reproducibles | Definición, items JSON versionados y hashes; estados controlados |
| Auditoría append-only | Evento con actor, entidad, before/after, razón, hash y contexto opcional |
| Sin borrado automático | Todas las FKs usan `ON DELETE RESTRICT` |

## 4. Garantías que requieren aplicación

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

## 5. Riesgos y limitaciones

- El DDL aún no ha sido interpretado por un servidor PostgreSQL real.
- Los 83 índices explícitos deben revisarse con consultas y volumen reales; algunos podrían ser
  redundantes o costosos en escritura.
- Los JSONB no tienen validación de esquema interna; su contrato vive versionado fuera del motor.
- Un CHECK no impide que un actor con permisos amplios edite evidencia histórica.
- La jerarquía de categorías solo impide auto-parentesco directo; ciclos largos requieren lógica adicional.
- La unicidad parcial de vocabularios vehiculares depende de marcar correctamente `review_status`.
- La zona de Odoo y el sistema 1900/1904 siguen sin confirmarse; los timestamps normalizados no
  deben poblarse definitivamente hasta resolverlos.
- La política futura de archivo y la ubicación inicial de imágenes siguen abiertas.
- `UNIQUE NULLS NOT DISTINCT` exige PostgreSQL 15+ y está cubierto por el objetivo PostgreSQL 16+.

## 6. Checklist manual previo a cualquier ejecución

- [ ] Confirmar PostgreSQL 16 o superior.
- [ ] Verificar hash y revisión aprobada de la migración.
- [ ] Confirmar que la base de destino esté vacía y sea la correcta.
- [ ] Confirmar respaldo y restauración cuando aplique.
- [ ] Revisar las 24 tablas y que no exista ninguna adicional.
- [ ] Revisar las 60 FKs y sus acciones restrictivas.
- [ ] Revisar 137 checks, 11 unique constraints y 83 índices explícitos.
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
