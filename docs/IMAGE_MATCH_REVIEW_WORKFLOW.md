# Revisión de candidatos imagen-producto

## Validación por lote

La consola permite aprobar o rechazar en una transacción hasta 500 asociaciones pendientes. El
formulario envía el conteo visto por el operador; el servidor vuelve a bloquear y consultar el
conjunto pendiente completo, exige que el conteo coincida y copia el `evidence_sha256` individual en
cada decisión. Si aparece o desaparece un candidato, el lote entero se revierte y obliga a recargar.

La decisión por lote no extrae, copia ni publica imágenes. La materialización content-addressed de
las asociaciones aprobadas continúa como una operación posterior y verificable.

La migración `0010` separa tres hechos que no deben confundirse:

1. una imagen fue indexada dentro de un ZIP en cuarentena;
2. su nombre coincide exactamente con una referencia interna primaria aprobada;
3. una persona aprobó o rechazó esa propuesta.

Ejecuta `ACTUALIZAR-SISTEMA.cmd` como administrador de PostgreSQL. El actualizador aplica la migración necesaria y crea
`image_product_candidate` e `image_product_decision`, ambas append-only y con permisos de la
aplicación limitados a `SELECT`/`INSERT`.

El algoritmo inicial `exact-approved-reference-v1` sólo normaliza el nombre base de la imagen y
lo compara con referencias internas aprobadas. No usa similitud difusa, no extrae el ZIP, no crea
`media_asset` y no escribe `product_media`. Cada candidato conserva un SHA-256 de su evidencia y
cada decisión humana queda vinculada a ese hash exacto.

La migración `0011` incorpora la materialización append-only. Tras una aprobación, la acción
individual vuelve a verificar el SHA-256 y tamaño del ZIP en cuarentena, el miembro, su CRC, tamaño
y SHA-256, y la evidencia exacta de candidato/decisión. Sólo entonces extrae una copia nueva y
content-addressed bajo `data/images/objects`; nunca modifica el ZIP original.

Tras aplicar `0010`, la cola está disponible en `http://127.0.0.1:8081/operator/images`.
Los candidatos se generan desde el índice mostrado en `Ingresos`; aprobar o rechazar sólo añade
una decisión append-only. El botón posterior `Materializar copia aprobada` es independiente,
idempotente y conserva su ruta y checksum en `approved_image_materialization`.

Los releases siguen siendo inmutables: una materialización no cambia releases existentes. Un release
nuevo captura la ruta, tipo y hash aprobados. Al exportarlo, el servidor vuelve a verificar el hash,
copia la imagen dentro del bundle y enumera esa copia en el manifiesto. El JSON de InDesign recibe
solamente la ruta relativa de esa copia autocontenida.
