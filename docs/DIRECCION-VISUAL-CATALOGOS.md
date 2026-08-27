# Dirección visual de catálogos

Fecha de investigación: 2026-08-27

## Objetivo

Construir catálogos de repuestos que combinen identidad de marca, lectura editorial y precisión técnica. El sistema debe producir desde el mismo release verificable una edición digital, un PDF y un paquete InDesign sin inventar datos ausentes.

## Referencias estudiadas

- [NSK Automotive Aftermarket](https://www.nskeurope.com/eu-en/products/automotive/automotive-aftermarket/catalogue-parts/): prioriza búsqueda por vehículo o número de pieza y fichas PDF con marca, modelo, año y referencia OE.
- [ZF Aftermarket](https://aftermarket.zf.com/en/aftermarket-portal/our-catalog/search-by-vehicle/): separa claramente marcas, vehículos, líneas de producto y documentación técnica.
- [Guía del catálogo ZF](https://aftermarket.zf.com/media/brazil/lancamentos/pdf_guia_de_uso_catalogo_zf_aftermarket.pdf): usa selección visual por logotipo de marca y navegación por segmento/montadora.
- [Catálogos FORVIA HELLA](https://www.hella.com/us/Catalogs-4323/): diferencia catálogo general, folleto de familia y ficha técnica; no intenta resolver todos los usos con una sola densidad de página.
- [Parker Racor Spare Parts Catalogue](https://pdf.nauticexpo.com/pdf/parker-hannifin/spare-parts-catalogue-truck-bus/21487-123418.html): incluye guía de uso, índice por referencia y tablas de aplicaciones/OEM con códigos de color por sección.
- [Brembo Parts](https://www.bremboparts.com/america/en): combina búsqueda por vehículo/código/medida con imagen, información técnica y documentación descargable.
- [TecDoc Catalogue](https://www.tecalliance.net/products/cards/tecdoc-catalogue): confirma que marca, artículo, vehículo y enlace de aplicación son entidades distintas; la búsqueda debe admitir vehículo, referencia de producto y OE.
- [Adobe InDesign Data Merge](https://helpx.adobe.com/uk/indesign/desktop/automation-and-scripting/merge-data/data-merging-overview.html): admite campos de texto, imágenes, previsualización de registros y QR de tipo URL desde la fuente de datos.

Las referencias de Behance y otros escaparates se usaron únicamente para observar composición, ritmo, espacios y jerarquía; las decisiones funcionales se basan en fabricantes y documentación oficial.

## Sistema visual propuesto

Cada marca tendrá un perfil independiente:

- nombre público y código estable;
- logotipo principal y variante monocroma;
- color principal, color secundario, tinta y fondo;
- eslogan opcional;
- dominio o URL base para QR;
- contraste validado para pantalla e impresión.

El color identifica la marca del producto. La marca vehicular (Toyota, Nissan, Chevrolet) se usa para navegación y aplicaciones, pero no cambia la identidad gráfica principal del catálogo.

## Familias de página

### P0 — Portada

- Logotipo de marca dominante.
- Año/versión y título del catálogo.
- Acento geométrico derivado de la paleta.
- Fotografía o ilustración técnica opcional, nunca obligatoria.
- Perfect Trading como editor/distribuidor en un nivel secundario.

### S — Separador de categoría o marca vehicular

- Nombre de sección grande.
- Color de marca y número de sección.
- Conteo de productos.
- Índice corto de subcategorías o modelos cuando exista.

### T4 — Cuadrícula compacta

- Cuatro productos por página.
- Imagen, referencia interna, nombre corto, OEM principal y una aplicación resumida.
- Adecuada para exploración rápida; aplicaciones extensas pasan a ficha T1 o tablas.

### T2 — Cuadrícula equilibrada

- Dos productos por página.
- Imagen mayor, varias referencias OEM y hasta tres aplicaciones visibles.
- Opción predeterminada para PDF comercial.

### T1 — Ficha individual

- Imagen principal grande.
- Referencia interna como dato más visible después del producto.
- Bloques separados de OEM, aplicaciones y especificaciones verificadas.
- QR hacia la ficha digital del release publicado.
- No mostrar precio, moneda, cantidad, inventario ni campos inexistentes.

### TABLE — Guía de aplicaciones

- Tabla densa ordenable por marca vehicular, modelo, año, motor, referencia Perfect y OEM.
- Repetición de encabezados y código de color por sección.
- Sirve como índice técnico; no reemplaza las fichas visuales.

## Reglas de composición

1. La referencia Perfect siempre se presenta con mayor contraste que el nombre descriptivo.
2. OEM y aplicaciones nunca se mezclan en un mismo párrafo.
3. Una aplicación debe conservar estructura: marca vehicular, modelo, años y motor cuando estén confirmados.
4. Las imágenes usan fondo neutro, escala consistente y `contain`; no se recortan piezas.
5. Los textos que desbordan cambian de T4 a T2/T1 o continúan en tabla; no se reducen hasta volverse ilegibles.
6. Cada exportación conserva release, versión y checksum en pie o metadatos, sin convertirlos en protagonistas visuales.
7. El QR se genera únicamente para una URL pública estable; nunca para rutas localhost.
8. La paleta personalizada debe pasar contraste mínimo antes de permitirse en exportación.

## Navegación digital

- Entrada por marca de producto.
- Filtros por categoría, marca vehicular, modelo, año, motor, referencia Perfect y OEM.
- Resultados visuales T4/T2 y ficha T1 al abrir un producto.
- Comparación opcional de dos referencias dentro de una categoría.
- Descarga de ficha PDF individual y enlace al catálogo completo.

## Orden de implementación

1. Perfiles de marca: CRUD auditado, logos y colores.
2. Selección de marca antes de preparar/importar; eliminar la constante NATSUKI del apply.
3. Tokens visuales comunes para HTML, PDF, PPTX e InDesign.
4. Plantillas P0, S, T4, T2, T1 y TABLE con previsualización real.
5. QR ligado a la ficha publicada.
6. Índices por referencia Perfect, OEM y aplicación vehicular.
7. Preflight de contraste, imágenes, desbordamiento, fuentes y enlaces.

## Criterio de aceptación visual

Una marca nueva debe poder configurarse sin modificar código. Al seleccionarla, la consola, la previsualización y todos los entregables deben usar el mismo logo y los mismos colores. Una misma referencia debe conservar exactamente sus OEM y aplicaciones en PDF, HTML e InDesign. Ningún formato puede mostrar datos de inventario o comerciales excluidos del alcance.
