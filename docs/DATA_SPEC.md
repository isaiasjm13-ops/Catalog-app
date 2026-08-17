# DATA_SPEC.md — Exportaciones Odoo v0.1

## Estado

Especificación preliminar basada en la muestra `EMPAQUE CABEZOTE.xlsx` de 237 productos.
No constituye todavía el contrato definitivo de importación.

## Campos observados

| Campo Odoo | Presencia | Tipo recomendado | Regla |
|---|---:|---|---|
| Nombre | 100% | `text` | Conservar valor original; no usar como clave única |
| Referencia interna | 100% | `text` | Conservar puntuación, espacios y ceros iniciales |

## Hallazgos

- Una hoja y dos columnas.
- Cero nulos en los campos exportados.
- 237 referencias internas únicas.
- Ocho nombres repetidos con referencias distintas.
- Aplicaciones, motores, años, posición, material y espesor están incrustados en el nombre.
- `/` tiene significados múltiples y no puede tratarse como separador universal.

## Contrato de staging

Toda importación futura debe registrar, antes de transformar:

- hash SHA-256 del archivo;
- nombre de hoja;
- fila de origen;
- encabezados originales;
- valores originales;
- hash de fila;
- versión de reglas;
- estado de validación y errores.

El staging es inmutable. Las normalizaciones y extracciones se guardan por separado.

## Identidad

La clave preferida será el ID estable de producto/variante de Odoo. Mientras no se exporte,
`marca + referencia interna normalizada` solo puede utilizarse como identidad provisional.
Nunca se deben fusionar registros por nombre.

## Campos requeridos en la próxima exportación

- ID de Odoo e ID externo;
- ID de plantilla e ID de variante;
- referencia interna y nombre;
- marca y categoría completa;
- activo y código de barras;
- unidad de medida;
- descripción de venta;
- fabricante, proveedor y referencia de proveedor;
- OEM, cross references y aplicaciones vehiculares disponibles;
- atributos de variante;
- fecha de última modificación.

## Reglas no negociables

- Odoo sigue siendo la fuente maestra.
- No modificar los archivos de origen.
- No eliminar productos automáticamente.
- Registrar candidatos de parsing con confianza y procedencia.
- Requerir revisión humana para datos ambiguos.
