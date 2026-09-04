# Revisión humana de identidades aplicadas

Estado: implementado y validado en PostgreSQL local. La migración `0006` está aplicada en
`perfect_catalog_dev`. No se ha revisado, activado ni rechazado ningún producto empresarial real.

## Propósito y estados

`apply-plan` crea cada producto, su referencia interna primaria y los candidatos A1 (OEM, FMSI,
adicionales y alternos) como pendientes. La revisión es una compuerta humana independiente:

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
estado actual y todos los campos visibles de la referencia primaria y las referencias A1. Si cualquiera cambia entre
inspección y decisión, la operación se rechaza.

## Garantías de base de datos

- Solo se admiten `pending_review → active|inactive` y `pending → approved|rejected`.
- Las columnas empresariales y de identidad permanecen inmutables durante la revisión.
- Producto y referencia deben llegar al estado correspondiente en una sola transacción.
- La misma decisión resuelve todas las A1 y aplicaciones vehiculares ligadas a la identidad; no se
  acepta una mezcla parcial de estados.
- El rol `perfect_catalog_app` no recibe `UPDATE` de tabla: solo de las columnas mínimas de estado y
  evidencia humana; no recibe `DELETE`.
- Cada decisión genera un evento append-only `catalog_identity.approved` o
  `catalog_identity.rejected` con el hash revisado.
- Una variante no puede aprobarse antes que su template.

El constructor de releases rechaza toda la marca si conserva identidades o referencias A1 pendientes; no puede
omitirlas silenciosamente y publicar un subconjunto accidental. Los productos rechazados quedan
fuera por estado, pero siguen preservados en la base y en auditoría.

## Límites vigentes

La inspección CLI completa está limitada explícitamente a 5,000 identidades. La consola web ya usa
una consulta set-based paginada y filtrable de 50 registros, por lo que no materializa 25,000
tarjetas a la vez ni ejecuta una consulta por identidad. El límite CLI falla de forma explícita; no
recorta ni aprueba parcialmente la cola.

Los controles de revisión viven en `INICIAR-REVISOR.cmd` y se documentan en
[`OPERATOR_WEB.md`](OPERATOR_WEB.md). El visor XLSX del piloto (`INICIAR-SERVER.cmd`) se retiró: leía
Excel directamente, sin pasar por cuarentena, dry-run ni aprobación. `INICIAR-CATALOGO-PUBLICADO.cmd`
y el HTML autónomo cubren hoy los casos de uso reales de consulta.
