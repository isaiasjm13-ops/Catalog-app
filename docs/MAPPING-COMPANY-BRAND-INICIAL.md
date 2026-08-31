# Mapping inicial Company / Brand - pendiente de aprobación

Este archivo es una hoja de decisión, no una migración. Debe completarse usando el informe generado
por `PREPARAR-MULTIEMPRESA.cmd` antes de escribir SQL estructural.

| Company propuesta | Brand confirmada | Código actual en BD | Política | Estado |
|---|---|---|---|---|
| Perfect Company | Perfect | PENDIENTE | Marcas propias de Perfect Company | Por verificar |
| KMC - King Motors Company | A1 | PENDIENTE | A1 pertenece exclusivamente a KMC | Por verificar |
| Natsuki | Natsuki | PENDIENTE | Company y Brand distintas con mismo nombre | Por verificar |
| Masaki | Masaki | PENDIENTE | Company y Brand distintas con mismo nombre | Por verificar |
| PDM | Marcas OEM por definir | PENDIENTE | Sólo marcas originales/OEM aprobadas | Bloqueado por lista |

## Decisiones que debe confirmar el informe y el usuario

- Código exacto de cada Brand existente y recuento de productos asociado.
- Marcas adicionales que pertenecen a Perfect Company, KMC, Natsuki y Masaki.
- Lista cerrada inicial de marcas OEM administradas por PDM.
- Tratamiento de marcas existentes que no coincidan con ninguna Company propuesta.
- Si `brand.code` debe ser único global o único dentro de Company.
- Company predeterminada para compatibilidad durante la migración gradual.
- Si Category deriva Company por sus productos o necesita pertenencia directa.

No se permite asignar automáticamente una marca desconocida ni ejecutar el backfill con filas
`PENDIENTE`.
