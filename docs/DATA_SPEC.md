# DATA_SPEC.md — Exportación maestra preliminar de Odoo v0.2

## Estado

Especificación preliminar basada en evidencia real de Odoo. Describe la exportación maestra
preliminar de NATSUKI para la familia de empaques, pero todavía no constituye el contrato
definitivo del esquema PostgreSQL ni del importador.

## Identificación de la fuente

| Propiedad | Valor |
|---|---|
| Sistema fuente | Odoo |
| Modelo | `product.template` |
| Marca | NATSUKI |
| Familia | Empaques |
| Archivo maestro local | `data/imports/NATSUKI_EMPAQUES_MAESTRO.xlsx` |
| SHA-256 | `a8921bc428cece3d318de189237384fc2119383febca57fdc9a86d47844407b8` |
| Fecha de integración | 2026-08-17 |
| Hoja | `Sheet1` |
| Rango utilizado | `A1:M894` |
| Filas de datos | 893 |
| Columnas | 13 |
| Fórmulas | 0 |

El archivo maestro local es una copia byte por byte del archivo recibido. El original y la
copia tienen el mismo SHA-256. Ningún proceso debe abrirlo para guardar, normalizarlo,
convertirlo ni modificarlo.

## Alcance de la exportación

Filtros empresariales aplicados en Odoo:

- `Marca = NATSUKI`;
- `Categoría de producto` contiene “empaque”.

No se aplicaron filtros de:

- cantidades;
- existencias o estado de stock;
- imágenes;
- código de barras.

La muestra incluye productos con cantidades positivas, cero o negativas, así como productos
con y sin imagen.

## Inventario de columnas y perfil observado

| # | Columna Odoo | Tipo observado | No nulos | Nulos | Completitud | Únicos exactos | Tratamiento preliminar |
|---:|---|---|---:|---:|---:|---:|---|
| 1 | Moneda | texto | 893 | 0 | 100% | 1 | Conservar el valor original y mapearlo a una moneda validada |
| 2 | Estado de la actividad | sin valores observados | 0 | 893 | 0% | 0 | Campo opcional; no inferir un estado cuando esté vacío |
| 3 | Categoría de producto | texto | 893 | 0 | 100% | 6 | Conservar la ruta original y normalizarla por separado |
| 4 | Favorito | booleano | 893 | 0 | 100% | 1 | Conservar como indicador de origen, sin usarlo como identidad |
| 5 | Nombre | texto | 893 | 0 | 100% | 868 | Conservar íntegro; no usar como clave única |
| 6 | Referencia interna | texto | 893 | 0 | 100% | 893 | Conservar puntuación, espacios significativos, guiones y ceros iniciales |
| 7 | # Variantes de producto | entero | 893 | 0 | 100% | 2 | Conservar como dato informativo de la plantilla |
| 8 | Cantidad real | entero | 893 | 0 | 100% | 265 | Tratar como fotografía temporal de inventario |
| 9 | Unidad de medida | texto | 893 | 0 | 100% | 1 | Conservar el valor original y resolverlo contra un catálogo validado |
| 10 | Cantidad disponible | entero | 893 | 0 | 100% | 262 | Tratar como fotografía temporal de inventario |
| 11 | Imagen 128 | texto o vacío | 711 | 182 | 79.62% | 631 | Clasificar estado y conservar el contenido original sin bloquear el producto |
| 12 | Última actualización el | número decimal de fecha/hora Excel | 893 | 0 | 100% | 108 | Conservar el valor original y convertirlo a fecha/hora solo con regla validada |
| 13 | Mostrar botón de estado de cantidad real | booleano | 893 | 0 | 100% | 1 | Conservar como indicador de origen, no como dato de identidad |

## Nulos y completitud

- `Estado de la actividad` está vacío en las 893 filas.
- `Estado de la actividad` no equivale al booleano `Activo` de Odoo; la exportación actual no
  contiene ese booleano y por tanto su estado de origen es desconocido (`source_active=NULL`).
- `Imagen 128` está vacío en 182 filas y presente en 711.
- Las otras 11 columnas están completas en las 893 filas.
- Un valor vacío debe conservarse como ausencia explícita; no se deben inventar valores por defecto durante staging.

## Duplicados

- No existen filas completamente duplicadas.
- `Referencia interna` contiene 893 valores no nulos y 893 valores únicos en esta muestra.
- `Nombre` contiene 868 valores únicos y 22 grupos de nombres duplicados.
- Los nombres repetidos pueden representar productos distintos.
- Nunca se deben fusionar productos únicamente por `Nombre`.

## Cantidades e inventario

`Cantidad real` y `Cantidad disponible` son una fotografía temporal tomada en el momento de
la exportación. No describen la identidad del producto ni determinan si debe existir en el
catálogo.

Reglas obligatorias:

- conservar valores positivos, cero y negativos;
- nunca excluir un producto por falta de stock;
- no utilizar cantidades en claves, conciliaciones ni deduplicación;
- registrar la fecha y la importación de procedencia de cada fotografía de inventario.

## Imágenes

`Imagen 128` puede:

- contener una representación Base64;
- estar vacía;
- contener mensajes o limitaciones originados por la exportación de Excel.

Un problema de imagen no debe impedir importar el producto. El importador debe clasificar el
estado de la imagen, registrar advertencias y continuar con los demás datos. Nunca debe
modificar ni eliminar imágenes originales de Odoo.

## Identidad provisional

Esta exportación no contiene un ID estable de Odoo ni un ID externo. Por ello:

- `Referencia interna` puede utilizarse provisionalmente como clave de conciliación porque las 893 referencias son únicas en esta muestra;
- esta decisión no convierte la referencia en una clave definitiva y debe revisarse antes de construir el importador;
- la identidad interna definitiva utiliza UUID estable; los IDs de producto o plantilla de Odoo,
  cuando estén disponibles, se conservan como identificadores contextuales para conciliación y
  nunca se usan directamente como PK interna;
- todas las referencias se almacenarán como texto, conservando ceros, guiones, espacios significativos y puntuación;
- nunca se utilizará `Nombre`, las cantidades ni el estado de imagen como identidad.

## Candidatos extraídos del Nombre

El texto de `Nombre` puede contener candidatos a:

- marca de vehículo;
- modelo;
- motor;
- cilindrada;
- años;
- posición o lado;
- material;
- medidas;
- observaciones.

Estos elementos no son hechos definitivos. Cada candidato extraído debe conservar:

- valor original;
- valor normalizado;
- regla y versión de regla utilizada;
- nivel de confianza;
- estado de revisión humana;
- fila e importación de procedencia.

Los separadores, abreviaturas y signos pueden tener significados múltiples. En particular,
`/` no debe tratarse como separador universal.

## Correspondencia con la arquitectura de datos v0.1

Esta especificación de evidencia sigue siendo preliminar como contrato de datos. La arquitectura
v0.1 que interpreta estas estructuras ya está aprobada documentalmente en `DATABASE_DESIGN.md`
y `IMPORTER_DESIGN.md`, pero no implementada. Antes de instalar PostgreSQL se debe producir y
revisar el DDL y la estrategia de migraciones.

### Registro de importaciones

Cada ejecución debe registrar:

- identificador interno de importación;
- nombre, tamaño y hash SHA-256 del archivo;
- fecha y hora de recepción y ejecución;
- sistema y modelo de origen;
- marca, familia, filtros y alcance declarados;
- versión del perfilador y de las reglas;
- estado de la ejecución;
- estadísticas de filas, columnas, nulos y duplicados;
- errores, advertencias y reporte generado.

### Staging inmutable

Cada fila de origen debe conservarse antes de transformar:

- importación de procedencia;
- nombre y número de hoja;
- número de fila original;
- encabezados y valores originales;
- representación JSON completa de la fila;
- hash de fila.

El staging es inmutable. Las correcciones, normalizaciones y extracciones se guardarán en
estructuras separadas y siempre apuntarán a la fila de origen.

### Resultados de procesamiento separados

Validación, normalización y conciliación se conservan en resultados append-only separados de
staging, versionados por fila, importación, contrato, reglas y etapa. Una versión nueva nunca
sobrescribe un resultado anterior. Los errores y advertencias permanecen en incidencias que
referencian la fila o el resultado correspondiente.

### Producto normalizado

El diseño preliminar debe contemplar:

- identidad interna del catálogo;
- ID estable de Odoo e ID externo cuando estén disponibles;
- referencia interna original y normalizada;
- nombre original;
- categoría original y normalizada;
- moneda y unidad de medida;
- cantidades y fecha de la fotografía de inventario;
- fecha de última actualización de Odoo;
- estado de imagen;
- marca, familia e importación de procedencia;
- estado de validación y revisión.

El estado interno del catálogo debe permanecer separado en `catalog_status`
(`pending_review/active/inactive/archived`). La presencia o ausencia en una exportación no
establece ni modifica automáticamente `source_active` o `catalog_status`.

### Datos relacionados

El modelo futuro debe poder relacionar con el producto:

- aplicaciones vehiculares candidatas;
- motores candidatos;
- años candidatos;
- referencias OEM y referencias cruzadas candidatas;
- imágenes y su estado de procesamiento;
- observaciones, advertencias y conflictos;
- evidencia, regla, confianza y revisión de cada candidato.

### Flujo y reglas del importador

1. Registrar la importación y verificar el hash del archivo.
2. Cargar todas las filas en staging inmutable.
3. Validar y persistir resultados versionados antes de normalizar o escribir productos.
4. Normalizar fuera de staging, conservando siempre el dato original y su procedencia.
5. Permitir nombres duplicados, productos sin imagen y stock cero o negativo.
6. Generar siempre un plan persistido antes de cualquier escritura empresarial, incluso si el modo solicitado es `apply`.
7. Someter el plan exacto a revisión y aprobación explícitas; `apply` solo puede ejecutar una vez
   el plan aprobado para el hash de archivo y las versiones de contrato/reglas registrados.
8. Realizar conciliación y `upsert` controlados, con cambios explícitos y auditables.
9. Nunca eliminar productos automáticamente.
10. Generar un reporte por importación.
11. Registrar cambios, errores, advertencias y conflictos.
12. Exigir revisión humana para coincidencias o extracciones ambiguas.

## Campos de fuente deseables (no son decisiones abiertas de arquitectura)

Para enriquecer futuras exportaciones conviene solicitar, cuando Odoo lo permita:

- ID de Odoo, ID externo, ID de plantilla e ID de variante;
- código de barras y estado activo;
- descripción de venta;
- fabricante, proveedor y referencia de proveedor;
- OEM, referencias cruzadas y aplicaciones vehiculares estructuradas;
- atributos de variante.

## Reglas no negociables

- Odoo sigue siendo la fuente maestra.
- No modificar los archivos de origen.
- No eliminar productos, imágenes ni referencias automáticamente.
- No excluir productos por stock o ausencia de imagen.
- No fusionar registros únicamente por nombre.
- Mantener trazabilidad completa desde el producto normalizado hasta la fila original.
- Requerir revisión humana para datos ambiguos.
