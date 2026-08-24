# Revisión humana de identidades aplicadas

Estado: implementado y validado en PostgreSQL local. La migración `0006` está aplicada en
`perfect_catalog_dev`. No se ha revisado, activado ni rechazado ningún producto empresarial real.

## Propósito y estados

`apply-plan` crea cada producto y su referencia interna primaria como pendientes. La revisión es
una compuerta humana independiente:

```text
producto pending_review + referencia pending
                   |
        +----------+----------+
        |                     |
     approve                reject
        |                     |
producto active       producto inactive
referencia approved   referencia rejected
```

No existe aprobación masiva implícita. Cada decisión requiere el UUID del producto, el fingerprint
del plan aplicado, el `review_sha256` exacto mostrado para esa ficha, actor y motivo. Una decisión
final no se sobrescribe; repetir exactamente la misma es idempotente y también verifica el hash
conservado en auditoría.

## Inspección y decisión

```powershell
# Solo lectura: devuelve una ficha y review_sha256 por identidad creada por el plan
.\.venv\Scripts\perfect-catalog.exe inspect-reviews <PLAN_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> --prompt-password

# Aprobar la ficha exacta inspeccionada
.\.venv\Scripts\perfect-catalog.exe review-product <PLAN_UUID> <PRODUCT_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> `
  --review-sha256 <REVIEW_SHA256_DE_LA_FICHA> `
  --decision approve --actor <USUARIO> `
  --reason "Nombre y referencia verificados contra la fuente" --prompt-password

# Rechazar sin borrar la identidad
.\.venv\Scripts\perfect-catalog.exe review-product <PLAN_UUID> <PRODUCT_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> `
  --review-sha256 <REVIEW_SHA256_DE_LA_FICHA> `
  --decision reject --actor <USUARIO> `
  --reason "Referencia incorrecta; requiere un plan sucesor" --prompt-password
```

El hash compromete plan y batch de origen, identidad estable, marca, nombre, variante, fila fuente,
estado actual y todos los campos visibles de la referencia primaria. Si cualquiera cambia entre
inspección y decisión, la operación se rechaza.

## Garantías de base de datos

- Solo se admiten `pending_review → active|inactive` y `pending → approved|rejected`.
- Las columnas empresariales y de identidad permanecen inmutables durante la revisión.
- Producto y referencia deben llegar al estado correspondiente en una sola transacción.
- El rol `perfect_catalog_app` no recibe `UPDATE` de tabla: solo de las columnas mínimas de estado y
  evidencia humana; no recibe `DELETE`.
- Cada decisión genera un evento append-only `catalog_identity.approved` o
  `catalog_identity.rejected` con el hash revisado.
- Una variante no puede aprobarse antes que su template.

El constructor de releases rechaza toda la marca si conserva identidades pendientes; no puede
omitirlas silenciosamente y publicar un subconjunto accidental. Los productos rechazados quedan
fuera por estado, pero siguen preservados en la base y en auditoría.

## Límites vigentes

La inspección por consola está limitada explícitamente a 5,000 identidades. Es suficiente para el
piloto actual de 893 filas, pero el catálogo objetivo supera 25,000 referencias: antes de abrir esa
escala se implementará una cola web paginada y filtrable. Este límite falla de forma explícita; no
recorta ni aprueba parcialmente la cola.

La web abierta por `INICIAR-SERVER.cmd` continúa siendo el visor XLSX del piloto. Todavía no expone
botones de revisión ni el catálogo PostgreSQL publicado. Esos controles serán la siguiente capa de
interfaz sobre este workflow ya protegido.
