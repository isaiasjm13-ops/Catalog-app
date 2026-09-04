# Workflow controlado de aprobación y apply

Estado: implementado y validado en PostgreSQL local con el rol de aplicación. Migraciones
`0003`–`0006` aplicadas; apply empresarial no autorizado.

Antes de resolver un producto, el plan debe contener una Company activa y una Brand activa de esa
Company. La resolución usa `source_system_id + brand_id + reference_type='internal' + value_normalized`.
`NO_CHANGE` no realiza escrituras empresariales. `CONFLICT` e `INVALID` no pueden aplicarse. `UPDATE`
se muestra con diff campo a campo y queda bloqueado por el contrato actual del trigger de revisión de
`product_template` hasta aprobar una migración posterior específica; los releases publicados no se
modifican para resolverlo.

## Límite de seguridad

El importador nunca escribe en Odoo ni modifica el XLSX/CSV fuente. El dry-run persiste evidencia y
un plan en `awaiting_review`; aprobar un plan tampoco crea productos. Solo `apply-plan`, después de
una aprobación humana separada, puede insertar registros empresariales en PostgreSQL.

Antes de cualquier prueba de base de datos se debe:

1. confirmar que `0001`–`0007` están aplicadas en el entorno objetivo;
2. ejecutar las 143 pruebas, incluidas las integraciones con rollback;
3. generar un plan nuevo con el contrato y las reglas actuales;
4. inspeccionar su reporte y resolver todos los bloqueos/conflictos;
5. obtener autorización humana para ese fingerprint exacto.

## Estados y evidencia

```text
awaiting_review --approve-plan--> approved --apply-plan--> applying --> applied
                                              error ------rollback----> approved
```

Ambos comandos vuelven a calcular:

- el hash canónico de cada item;
- `plan_sha256` en el orden persistido;
- el fingerprint sobre archivo, contrato, reglas y plan;
- el SHA-256 del archivo físico.

La operación se rechaza si difiere cualquiera de ellos, si el contrato/reglas no son los actuales,
si falta actor o motivo, o si el estado no permite la transición. La aprobación queda registrada en
`audit_event`; la creación de productos, snapshots y el cierre del plan comparten un `correlation_id`.

## Alcance actual del apply

Admitido:

- `create`: producto nuevo y referencia interna pendiente de revisión;
- `inventory_snapshot`: solo con cantidades y unidad completas, ligado a un producto creado por el
  mismo plan;
- `media_pending`: conserva el trabajo pendiente sin decodificar Base64;
- `no_change`: no escribe datos empresariales.

Bloqueado antes de escribir:

- `update`: falta una comparación segura campo por campo y `before_values` completo;
- `blocked` y `conflict`: requieren corregir/reconciliar y generar otro plan;
- cualquier operación desconocida o snapshot huérfano.

No se conceden permisos DELETE. El rol de aplicación solo puede actualizar las columnas de estado y
evidencia necesarias, e insertar las entidades producidas por este flujo.

## Idempotencia y recuperación

El plan se bloquea con `FOR UPDATE` y el apply usa una transacción serializable. Si todas las
escrituras terminan, el estado pasa a `applied`. Una llamada posterior con el mismo fingerprint
válido responde `already_applied` y no repite inserts.

Una excepción revierte el cambio a `applying` y todas las inserciones de esa llamada, por lo que el
plan permanece `approved` y puede investigarse/reintentarse. No se debe reparar el estado a mano ni
editar un plan persistido: cualquier cambio requiere generar un plan sucesor revisable.

## Comandos

```powershell
.\.venv\Scripts\perfect-catalog.exe inspect-plan <PLAN_UUID> --prompt-password

.\.venv\Scripts\perfect-catalog.exe approve-plan <PLAN_UUID> `
  --fingerprint <SHA256> --actor <USUARIO> --reason "Motivo verificable" --prompt-password

.\.venv\Scripts\perfect-catalog.exe apply-plan <PLAN_UUID> `
  --fingerprint <MISMO_SHA256> --actor <USUARIO> --reason "Autorización de apply" --prompt-password
```

Estos comandos no deben ejecutarse sobre un plan empresarial sin autorización humana expresa para
ese plan y fingerprint exactos. La validación sintética no transfiere autorización a datos reales.

Aplicar un plan no publica automáticamente un catálogo. La construcción y publicación de
`catalog_release` usa una compuerta posterior, separada e inmutable; sus reglas están en
[`RELEASE_PUBLICATION_WORKFLOW.md`](RELEASE_PUBLICATION_WORKFLOW.md) y el contrato de lectura en
[`RELEASE_READ_MODEL.md`](RELEASE_READ_MODEL.md).

Tampoco activa productos. Después de `apply-plan`, cada identidad y su referencia interna primaria
deben resolverse individualmente mediante el workflow con evidencia criptográfica descrito en
[`PRODUCT_REVIEW_WORKFLOW.md`](PRODUCT_REVIEW_WORKFLOW.md). La migración `0006` concede solamente
las columnas de esa transición, bloquea cambios de datos de catálogo y exige que producto y
referencia terminen alineados dentro de la misma transacción.

La interfaz protegida y paginada para ejecutar esas decisiones está documentada en
[`OPERATOR_WEB.md`](OPERATOR_WEB.md). Su existencia no autoriza aplicar un plan empresarial.
