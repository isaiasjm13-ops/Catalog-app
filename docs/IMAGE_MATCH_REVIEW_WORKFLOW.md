# Revisión de candidatos imagen-producto

La migración `0010` separa tres hechos que no deben confundirse:

1. una imagen fue indexada dentro de un ZIP en cuarentena;
2. su nombre coincide exactamente con una referencia interna primaria aprobada;
3. una persona aprobó o rechazó esa propuesta.

Ejecuta `MIGRAR-REVISION-IMAGENES.cmd` como administrador de PostgreSQL. La migración crea
`image_product_candidate` e `image_product_decision`, ambas append-only y con permisos de la
aplicación limitados a `SELECT`/`INSERT`.

El algoritmo inicial `exact-approved-reference-v1` sólo normaliza el nombre base de la imagen y
lo compara con referencias internas aprobadas. No usa similitud difusa, no extrae el ZIP, no crea
`media_asset` y no escribe `product_media`. Cada candidato conserva un SHA-256 de su evidencia y
cada decisión humana queda vinculada a ese hash exacto.

La materialización de una asociación aprobada será un bloque posterior y separado: deberá volver
a verificar ZIP, entrada, CRC/SHA-256 y decisión antes de extraer una copia content-addressed.
