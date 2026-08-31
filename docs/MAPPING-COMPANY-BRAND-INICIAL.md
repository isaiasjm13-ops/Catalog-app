# Mapping inicial Company / Brand - pendiente de aprobación

Este archivo es una hoja de decisión, no una migración. Debe completarse usando el informe generado
por `PREPARAR-MULTIEMPRESA.cmd` antes de escribir SQL estructural.

| Company propuesta | Brand confirmada | Código actual en BD | Política | Estado |
|---|---|---|---|---|
| Perfect Company | Perfect | PENDIENTE | Marcas propias de Perfect Company | Por verificar |
| KMC - King Motors Company | A1 | PENDIENTE | A1 pertenece exclusivamente a KMC | Por verificar |
| Natsuki | Natsuki | NATSUKI (193 productos) | Company y Brand distintas con mismo nombre | Verificado en BD |
| Masaki | Masaki | PENDIENTE | Company y Brand distintas con mismo nombre | Por verificar |
| PDM | Marcas OEM por definir | PENDIENTE | Sólo marcas originales/OEM aprobadas | Bloqueado por lista |
| Perfect Company | Exact Cars | EXACTCARS (279 productos) | Pertenece a Perfect Company | Confirmado por usuario |

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

## Evidencia de la base del 2026-08-31

- 472 productos activos: 193 Natsuki y 279 Exact Cars.
- Dos releases publicados: uno Natsuki y uno Exact Cars, con 472 items en total.
- Dos perfiles y dos revisiones visuales, ambos de scope `brand`; no existe identidad `company`.
- 472 referencias internas aprobadas; no hay referencias cruzadas ni duplicados normalizados.
- Perfect, A1 y Masaki no existen todavía como Brand en la base auditada.

## Evidencia complementaria del archivo de imágenes

El inventario de red se documenta en
[`INVENTARIO-CARPETAS-MARCAS-2026-08-31.md`](INVENTARIO-CARPETAS-MARCAS-2026-08-31.md).
Las carpetas aportan candidatos, no autoridad comercial. `ASIA INC` y `KDT` aparecen tanto bajo
Perfect como bajo PDM; `KMC`, `MASAKI` y `NATSUKI` aparecen bajo Perfect pese a que la
especificación los trata como Companies. Todos quedan pendientes de conciliación con Odoo.
