# Workflow controlado de publicación de releases

Estado: implementado y validado en PostgreSQL local con el rol `perfect_catalog_app`. La migración
`0005` está aplicada. No se construyó ni publicó ningún release empresarial.

## Separación de decisiones

El flujo conserva tres decisiones independientes:

1. `apply-plan` inserta datos revisados en PostgreSQL, pero no los activa ni publica;
2. `build-release` congela un borrador exacto y devuelve su checksum;
3. `publish-release` exige aprobación humana del checksum exacto.

Archivar es una cuarta transición explícita. Reintentar el mismo build, publish o archive devuelve
`already_built`, `already_published` o `already_archived` sin repetir escrituras.

## Elegibilidad del borrador

La construcción exige:

- un plan en estado `applied`, con fingerprint, items y versiones todavía íntegros;
- una única marca solicitada dentro del sistema fuente del plan;
- productos template `active`;
- si el template tiene variantes, al menos una variante `active` y un item por variante activa;
- exactamente una referencia `internal`, primaria y `approved` por identidad publicada;
- UUID público único dentro del release.

El inventario más reciente se congela cuando existe; su ausencia permanece nula. Solo un medio
primario procesado se declara `present`. Los productos pendientes, inactivos o sin referencia
aprobada no se publican silenciosamente: si una identidad candidata carece de una referencia única,
la construcción completa se rechaza.

## Integridad e inmutabilidad

`catalog-product-v1` calcula un SHA-256 por item. `catalog-release-v2` cubre la definición, marca,
versión, orden, identidades, schemas y hashes de todos los items. La definición exige y conserva el
plan, fingerprint, batch, contrato, reglas, selección y conteo exacto que originaron el snapshot;
el lector también valida este contrato antes de servir datos.

La migración `0005` añade:

- inserción de releases únicamente como borradores completos;
- bloqueo de `UPDATE`/`DELETE` sobre items y `DELETE` sobre releases;
- transiciones exclusivas `draft → published → archived`;
- auditoría append-only;
- índice único por identidad pública dentro del release;
- permisos INSERT y UPDATE por columna mínimos para `perfect_catalog_app`.

Los triggers también protegen contra escrituras realizadas fuera de la CLI. Al publicar una nueva
versión de una marca, cualquier versión publicada anterior se valida y archiva en la misma
transacción, con eventos correlacionados.

## Comandos

```powershell
# 1. Construir borrador desde un plan aplicado y un catálogo ya revisado/activo
.\.venv\Scripts\perfect-catalog.exe build-release <PLAN_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> --version <VERSION> --brand NATSUKI `
  --actor <USUARIO> --reason "Motivo verificable" --prompt-password

# 2. Inspeccionar estado, definición, conteo y checksum
.\.venv\Scripts\perfect-catalog.exe inspect-release <RELEASE_UUID> --prompt-password

# 3. Publicar únicamente el checksum revisado
.\.venv\Scripts\perfect-catalog.exe publish-release <RELEASE_UUID> `
  --snapshot-sha256 <SHA256> --actor <USUARIO> `
  --reason "Publicación autorizada" --prompt-password

# 4. Archivar sin alterar contenido
.\.venv\Scripts\perfect-catalog.exe archive-release <RELEASE_UUID> `
  --snapshot-sha256 <MISMO_SHA256> --actor <USUARIO> `
  --reason "Versión sustituida" --prompt-password
```

No se deben ejecutar estos comandos sobre datos empresariales sin autorización expresa para el
plan, la versión y el checksum concretos. La validación sintética con rollback no transfiere esa
autorización.

## Recuperación

Todas las operaciones usan transacciones serializables. Un error revierte borrador, items,
transición y auditoría juntos. Un release incorrecto no se edita ni se borra: se conserva como
borrador y la corrección genera otra versión. Una publicación incorrecta se archiva mediante la
transición auditada y se sustituye por un release nuevo.
