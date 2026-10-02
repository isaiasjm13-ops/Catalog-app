# Diseño de migración multiempresa - previo a SQL

Estado: diseño y mapping inicial aprobados; migraciones 0017-0018 preparadas, pendientes de aplicar.

## Decisiones mínimas recomendadas

1. Mantener FastAPI y el esquema `perfect_catalog`.
2. Crear `company` sin crear `corporation` en la primera fase. Corporation no aporta aislamiento
   inmediato y puede añadirse después sin reinterpretar productos.
3. Company se deriva autoritativamente desde `brand.company_id`. No añadir todavía `company_id` a
   Product ni Category: duplicaría pertenencia y exigiría coherencia adicional.
4. Conservar `brand.code` único globalmente durante la transición. Es compatible con los datos y
   evita cambiar URLs, importaciones y releases. Evaluar unicidad por Company sólo ante un caso real.
5. Mantener categorías como taxonomía compartida. El aislamiento de productos se realiza mediante
   Brand->Company; una categoría no concede acceso a productos.
6. Asociar cada revisión visual de scope `company` a una Company concreta. La consulta global
   “última company” debe desaparecer antes de activar más de una empresa.
7. Añadir Company a `catalog_release` sólo como snapshot/denormalización comprobable o derivarla
   desde Brand. Para la primera fase se recomienda derivar y congelar el identificador en
   `definition`, evitando dos fuentes mutables.

## Ledger de migraciones

Antes de 0017 se recomienda una tabla administrada por owner:

- `migration_id` textual (`0017_companies`);
- `checksum_sha256` del SQL aprobado;
- `applied_at`, `applied_by`, `postgres_version`;
- `execution_id` UUID y notas.

El actualizador debe comprobar checksum: misma ID con otro checksum es error bloqueante. Las
migraciones 0001-0016 se registrarán como baseline observado, sin volver a ejecutarlas.

## Etapas de 0017 propuestas

### 0017A - estructura compatible

- Crear `company` con código, nombre, estado y auditoría.
- Insertar Companies confirmadas mediante IDs deterministas.
- Añadir `brand.company_id` nullable y FK `RESTRICT`.
- Añadir índice `(company_id, is_active, normalized_name)`.
- No modificar todavía unicidad ni consultas productivas.

### 0017B - backfill explícito

- Archivo separado con mapping por `brand_id`, no por coincidencia débil de nombre.
- NATSUKI y MASAKI se asignan a Perfect Trading como marcas de producto; no son Companies.
- EXACTCARS se asigna a Perfect Company por confirmación explícita del usuario.
- Verificar que cero marcas activas queden sin Company.

### 0017C - integridad

- Hacer `brand.company_id NOT NULL` sólo con verificación cero-null.
- Adaptar creación/importación para exigir Company y Brand perteneciente.
- Añadir pruebas negativas de relación cruzada y permisos SQL mínimos.

### 0018 - identidad y contexto

- Añadir `company_id` nullable a `visual_identity_revision`.
- Migrar revisiones corporativas sólo con mapping explícito (hoy no existen filas scope company).
- Cambiar constraint de scope para exigir un único destino.
- Implementar `CompanyContext` en sesión y gateway, inicialmente detrás de feature flag.

## Validación y rollback

- Backup custom legible + SHA-256 antes de cada etapa.
- Ejecutar cada etapa en transacción con `ON_ERROR_STOP`.
- Comparar filas, releases y hashes antes/después; releases históricos no cambian.
- 263 pruebas unitarias más integraciones PostgreSQL y nuevas pruebas de aislamiento.
- Antes de 0017C, rollback lógico: desactivar feature flag y retirar columnas nullable en una
  migración inversa aprobada. Después de NOT NULL, rollback primario: restaurar el dump verificado.

## Decisiones abiertas posteriores

- Lista de Brands OEM de PDM.
- Company predeterminada para la transición.
- Confirmación de que códigos de Brand seguirán siendo globalmente únicos.
