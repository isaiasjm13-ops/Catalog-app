# Fuentes oficiales de logos vehiculares

Verificado el 31 de agosto de 2026. El directorio siguiente cubre las fuentes comprobadas
manualmente; no pretende conceder derechos sobre los activos.

El parser v3 reconoce 100 marcas normalizadas y 122 alias. La cobertura se mantiene en
`src/perfect_catalog/vehicle_makes.py` y se basa en fabricantes probables para catálogos de
repuestos de América Latina, Norteamérica, Europa y Asia. Se contrastó la metodología con la API
vehicular oficial vPIC de NHTSA y con la clasificación de fabricantes del JRC europeo. No se copió
el catálogo completo de vPIC porque incluye fabricantes legales, carroceros y remolques que
producirían falsos positivos.

## Regla de uso

- Descargar únicamente desde el sitio corporativo, la sala de prensa o el portal de marca del fabricante.
- Preferir SVG oficial; si no está disponible, PNG transparente de alta resolución.
- No redibujar, recolorear, deformar ni retirar el área de seguridad del logo.
- Confirmar que el uso comercial en un catálogo propio está autorizado. Que un archivo sea descargable no implica permiso comercial: por ejemplo, Toyota prohíbe copiar sus logos y Volkswagen identifica ciertos recursos solo para uso editorial.
- Guardar en la consola el enlace de origen dentro del motivo auditable al cargar el activo.

## Directorio verificado

| Marca | Fuente oficial actual | Observación |
|---|---|---|
| Toyota | https://global.toyota/en/mobility/toyota-brand/features/emblem/ | Emblema actual explicado por Toyota. Sus términos restringen la descarga/copia del logo; solicitar autorización o activo al distribuidor. |
| Nissan | https://global.nissannews.com/ | Sala de prensa global oficial; validar condiciones del activo elegido. |
| Mitsubishi | https://www.mitsubishi-motors.com/en/company/ | Sitio corporativo oficial de Mitsubishi Motors. |
| Honda | https://global.honda/en/newsroom/news/2026/c260113eng.html | Honda anunció un H renovado en 2026 para vehículos futuros; no sustituir automáticamente el emblema vigente en todo el catálogo. |
| Hyundai | https://www.hyundai.com/kr/ko/info/ci | Página CI oficial con variantes, espacio mínimo y reglas de color. |
| Chevrolet | https://media.chevrolet.com/Pages/galleries/us/en/logos.html?page=1 | Galería oficial de logos de Chevrolet/GM. |
| Ford | https://corporate.ford.com/about/history/company-timeline/ | Fuente corporativa oficial sobre el Blue Oval; pedir el paquete de marca vigente si no ofrece descarga. |
| Mazda | https://newsroom.mazda.com/en/publicity/release/2025/202510/251029a.html | Mazda comenzó a desplegar un símbolo y wordmark renovados en 2025; usar la variante adecuada al medio. |
| Kia | https://worldwide.kia.com/en/brand/our-brand/brand-elements/brand-logo-story | Fuente ideal: incluye descarga explícita del logo oficial actual. |
| Volkswagen | https://www.volkswagen-newsroom.com/en/images/detail/volkswagen-unveils-new-brand-design-and-logo-30063 | Logo 2D oficial; el recurso indicado es de uso editorial. |
| Suzuki | https://www.globalsuzuki.com/globalnews/2025/0922.html | Nuevo emblema anunciado en 2025; confirmar si corresponde al mercado/modelo del catálogo. |
| Renault | https://www.renaultgroup.com/en/magazine/our-group-news/a-renaulution-for-the-diamond/ | Diamante oficial vigente, desplegado en toda la gama desde 2024. |
| Chery | https://www.cheryinternational.com/pc/aboutchery/introduction/ | Sitio global oficial; pedir el archivo maestro vigente si no ofrece descarga pública. |
| Geely | https://global.geely.com/en/brand | Página oficial de marca de Geely Auto Group. |
| Great Wall / GWM | https://www.gwm.com.my/en/media-center/logos/logos | Centro de medios oficial regional con logos; contrastar con https://www.gwm-global.com/ antes de cargarlo. |

## Carga en Perfect Catalog

1. Iniciar `INICIAR-REVISOR.cmd`.
2. Abrir **Marcas** y bajar a **Logos de marcas vehiculares**.
3. Elegir la marca, subir el archivo y escribir en el motivo la fuente oficial y fecha de revisión.
4. Construir una versión nueva del catálogo. Los releases anteriores son inmutables.

Los logos vehiculares aparecen solamente junto al nombre de la marca del vehículo. No reemplazan el logo de la empresa ni la marca del producto.

## Logos todavía no verificados

Una marca reconocida por el parser no recibe un logo inventado ni descargado de agregadores. Cuando
aparezca por primera vez, queda como sugerencia pendiente. Tras aprobarla, se habilita en **Marcas →
Logos de marcas vehiculares**, donde debe cargarse el archivo entregado por el fabricante,
distribuidor o centro de prensa oficial. El reconocimiento del parser funciona aunque todavía no
exista logo.
