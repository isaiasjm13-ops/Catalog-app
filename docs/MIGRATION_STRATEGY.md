# Estrategia de migraciones PostgreSQL

> **Versión v0.1 — Documental — PostgreSQL todavía no instalado**

Esta estrategia acompaña `db/migrations/0001_initial_schema.sql`. El DDL es revisable pero no
ha sido ejecutado. No existe todavía ninguna tabla real ni se ha instalado Alembic.

## 1. Principios

1. Las migraciones son **forward-only**: una corrección se entrega en una migración posterior.
2. Cada archivo representa un cambio lógico pequeño, explicable y revisable.
3. Una migración aplicada no se edita, renombra ni reemplaza.
4. El SQL se revisa antes de aplicarse y se prueba primero fuera de producción.
5. Toda migración se ejecuta dentro de una transacción cuando PostgreSQL lo permita.
6. Los UUID se suministran desde la aplicación; ninguna migración depende de extensiones.
7. No se incorporan credenciales, datos empresariales ni rutas privadas en los archivos SQL.
8. La evidencia, staging, snapshots, planes aplicados y auditoría no se eliminan como atajo operativo.

## 2. Convención y secuencia

- Directorio: `db/migrations/`.
- Nombre: número de cuatro dígitos, guion bajo y descripción snake_case.
- Primera migración: `0001_initial_schema.sql`.
- Ejemplos posteriores: `0002_add_supplier_reference.sql`, `0003_index_product_search.sql`.
- La numeración es monotónica y nunca se reutiliza.
- Cada migración declara al inicio su objetivo, precondiciones y compatibilidad mínima.

La aplicación futura mantendrá un orden único. Antes de adoptar Alembic, el registro de qué se
ejecutó deberá quedar en el procedimiento de despliegue y en la evidencia de revisión; no se
creará una tabla paralela improvisada dentro de esta fase documental.

## 3. Entornos

| Entorno | Propósito | Datos permitidos | Criterio de promoción |
|---|---|---|---|
| Local | Desarrollo y validación inicial | Sintéticos o copias autorizadas/protegidas | SQL revisado y pruebas estáticas aprobadas |
| Prueba | Ensayo reproducible de migración y aplicación | Dataset de prueba controlado | Migración real exitosa, constraints e índices verificados |
| Producción | Operación empresarial | Datos autorizados | Aprobación formal, respaldo comprobado y ventana de cambio |

La promoción conserva exactamente el mismo archivo y hash de migración entre entornos. No se
mantienen variantes manuales del SQL por ambiente.

## 4. Flujo de aprobación

1. Redactar la migración y su motivación.
2. Ejecutar pruebas estáticas y `git diff --check`.
3. Revisar nombres, tipos, constraints, índices, bloqueos previstos y volumen afectado.
4. Confirmar que el archivo no contiene secretos ni datos empresariales.
5. Revisar el plan en local y después en prueba contra la versión soportada de PostgreSQL.
6. Registrar resultados, duración, locks observados y hash del archivo.
7. Obtener aprobación del Coordinador y del responsable de datos.
8. Crear un respaldo verificable antes de cualquier cambio destructivo o de difícil reversión.
9. Ejecutar en la ventana aprobada y validar métricas posteriores.

La aprobación de una versión no se transfiere automáticamente a un archivo modificado. Todo
cambio de contenido invalida la revisión anterior.

## 5. Cambios de columnas

- **Agregar nullable:** normalmente compatible; añadir validaciones y backfill por separado.
- **Agregar NOT NULL:** primero crear nullable, poblar por lotes, validar y finalmente imponer
  la restricción en otra migración.
- **Cambiar tipo:** usar una columna nueva o conversión explícita probada; evitar conversiones
  implícitas que puedan truncar o reinterpretar datos.
- **Renombrar:** mantener temporalmente compatibilidad con lectores/escritores durante el despliegue.
- **Retirar:** confirmar que no existen consumidores ni evidencia requerida antes de una futura
  migración contract aprobada.

Los valores originales de Odoo y seriales de Excel se preservan. Una nueva interpretación de
fechas crea resultados versionados; no reescribe staging.

## 6. Índices y constraints

- Crear únicamente índices respaldados por consultas o reglas de integridad conocidas.
- Evitar GIN sobre JSONB hasta tener una consulta y medición que lo justifiquen.
- Para índices grandes se evaluará `CREATE INDEX CONCURRENTLY`; como no puede ejecutarse dentro
  de una transacción normal, deberá aislarse, documentarse y tener un procedimiento específico.
- Agregar FKs/checks costosos mediante una fase compatible y validarlos posteriormente cuando el
  volumen lo requiera.
- Medir locks, tiempo, espacio adicional y efecto en escrituras antes de producción.

## 7. Backfills y expand/migrate/contract

Los cambios incompatibles siguen tres fases:

1. **Expand:** agregar columnas, tablas o índices compatibles sin retirar el contrato anterior.
2. **Migrate:** desplegar código capaz de ambos contratos y ejecutar backfill idempotente por lotes,
   con checkpoints, métricas y auditoría.
3. **Contract:** retirar el contrato anterior solo después de comprobar que ningún consumidor lo usa.

Cada backfill debe declarar clave de avance, tamaño de lote, política de reintento, verificación de
conteos y mecanismo para detenerse. Nunca debe alterar evidencia original para “normalizarla”.

## 8. Rollback y migraciones fallidas

- El rollback normal es una **migración compensatoria** revisada, no un borrado improvisado.
- Si falla una migración transaccional, PostgreSQL revierte la transacción completa; se conserva
  el error y se corrige en un archivo nuevo.
- Si una operación no transaccional falla, se detiene la promoción, se inspecciona el estado real
  y se redacta una compensación explícita antes de reintentar.
- Restaurar un respaldo es una decisión operacional excepcional con autorización, ventana y
  validación posterior; no sustituye el diseño de compatibilidad.
- Una migración parcialmente ejecutada nunca se marca como completada por conveniencia.

## 9. Versionado de contratos

- `contract_version` identifica el contrato de columnas de entrada.
- `rules_version` identifica normalización, validación, conciliación y extracción.
- `staging_row` permanece inmutable y sin versión mutable interna.
- `staging_row_result` conserva contrato, reglas, etapa, intento y hash de cada resultado.
- `snapshot_schema_version` versiona el JSON canónico de publicaciones.
- Una modificación de contrato, reglas o snapshot exige compatibilidad explícita o migración.

## 10. Adopción futura de Alembic

Alembic se adoptará cuando comience la implementación de FastAPI. En ese momento:

- se instalará y configurará mediante una tarea separada y aprobada;
- `alembic_version` será administrada exclusivamente por Alembic;
- la migración inicial se incorporará como baseline verificado;
- las revisiones autogeneradas se tratarán como borradores y requerirán revisión humana;
- no se editarán revisiones que ya hayan sido aplicadas en un entorno compartido.

Esta fase no instala Alembic, no crea su configuración y no crea `alembic_version`.

## 11. Próxima validación antes de ejecutar

1. Revisión manual usando `docs/DDL_REVIEW.md`.
2. Instalación posterior y separada de PostgreSQL 16+ en el entorno local.
3. Ejecución de la migración en una base vacía de prueba.
4. Inspección del catálogo PostgreSQL para confirmar tablas, FKs, checks e índices.
5. Pruebas de inserción sintética, rechazo de datos inválidos y rollback transaccional.
6. Registro del tiempo de ejecución y de cualquier ajuste requerido en una nueva migración.
