# Mapping inicial Company / Brand

Este archivo registra la jerarquía confirmada. La migración `0021_company_administration.sql`
corrige el sembrado histórico que había creado Natsuki y Masaki como empresas.

| Company propuesta | Brand confirmada | Código actual en BD | Política | Estado |
|---|---|---|---|---|
| Perfect Trading | Perfect | PENDIENTE | Marca propia de Perfect Trading | Por verificar |
| KMC - King Motors Company | A1 | PENDIENTE | A1 pertenece exclusivamente a KMC | Por verificar |
| Perfect Trading | Natsuki | NATSUKI (193 productos) | Natsuki es marca de producto, no empresa | Confirmado por usuario |
| Perfect Trading | Masaki | PENDIENTE | Masaki es marca de producto, no empresa | Confirmado por usuario |
| PDM | Marcas OEM por definir | PENDIENTE | Sólo marcas originales/OEM aprobadas | Bloqueado por lista |
| Perfect Trading | Exact Cars | EXACTCARS (279 productos) | Pertenece a Perfect Trading | Confirmado por usuario |

## Decisiones que debe confirmar el informe y el usuario

- Código exacto de cada Brand existente y recuento de productos asociado.
- Marcas adicionales que pertenecen a Perfect Trading, KMC y PDM.
- Lista cerrada inicial de marcas OEM administradas por PDM.
- Tratamiento de marcas existentes que no coincidan con ninguna Company propuesta.
- Si `brand.code` debe ser único global o único dentro de Company.
- Company predeterminada para compatibilidad durante la migración gradual.
- Si Category deriva Company por sus productos o necesita pertenencia directa.

No se permite asignar automáticamente una marca desconocida ni convertir una marca de producto en
empresa. Las filas pendientes requieren confirmación antes de materializarse.

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
Perfect como bajo PDM. La ubicación de `MASAKI` y `NATSUKI` bajo Perfect coincide con la jerarquía
confirmada; las carpetas siguen siendo evidencia auxiliar y no crean empresas automáticamente.
