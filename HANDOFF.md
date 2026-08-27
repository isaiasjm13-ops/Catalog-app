# HANDOFF.md - Estado de Traspasos Entre Sesiones

## Bloque 2026-08-27: búsqueda móvil y offline v1.18

- El HTML ligero y el autónomo incorporan un buscador interno fijo al desplazarse. Filtra en tiempo
  real por todo el texto editorial de cada ficha: referencia, nombre, categoría, marca, OEM,
  aplicaciones y motor; ignora mayúsculas y acentos.
- La búsqueda funciona completamente en el navegador, sin servidor, red ni envío de consultas. En
  móvil usa un campo de 48 px, teclado de búsqueda, contador de resultados y botón para limpiar.
- El catálogo oculta fichas y secciones sin coincidencias, conserva carga diferida de imágenes y el
  visor de fotografía completa. Los HTML ya exportados deben regenerarse.
- Verificación: 53 pruebas focalizadas y 252 pruebas completas pasan; 6 integraciones PostgreSQL se
  omiten sin credenciales.

## Bloque 2026-08-27: visor de imágenes del catálogo digital v1.17

- Cada fotografía del HTML ligero y del HTML autónomo es ahora pulsable y abre un visor a tamaño
  de pantalla. Tanto la miniatura como la ampliación usan encaje proporcional `contain`, por lo que
  muestran el producto completo sin recorte ni deformación.
- El visor funciona sin JavaScript mediante enlaces y `:target`: se cierra desde el botón visible o
  pulsando el fondo. Conserva accesibilidad por teclado, oculta la capa al imprimir y no cambia la
  política de seguridad ni la portabilidad del archivo autónomo.
- Los catálogos ya generados son inmutables y deben exportarse nuevamente para incluir el visor.
- Verificación focalizada: 53 pruebas pasan (exportación, operador y empaquetado). Suite completa:
  252 pruebas pasan y 6 integraciones PostgreSQL se omiten sin credenciales.

## Bloque 2026-08-27: auditoría técnica y visual

- Auditoría registrada en `docs/AUDIT-2026-08-27.md` con prioridades, decisiones y referencias
  oficiales W3C/Adobe.
- PDF/PPTX usan copias raster limitadas a su tamaño de presentación, con orientación EXIF, encaje
  proporcional y JPEG progresivo; los originales aprobados y el paquete InDesign siguen intactos.
  El último PDF anterior a esta corrección medía aproximadamente 105 MB y debe regenerarse para
  medir la reducción real.
- Los errores de imagen en PDF/PPTX ya no se omiten silenciosamente. InDesign TABLE respeta 12 pt y
  las fichas incluyen tipo de pieza y motor.
- La consola suma navegación por teclado visible, salto al contenido y objetivos de 44 px. Los
  perfiles nuevos validan contraste WCAG AA 4.5:1.
- Los manifiestos nuevos conservan conteos de productos con/sin imagen, imágenes únicas y bytes.

## Bloque 2026-08-27: preparación asistida y control de imágenes v1.14

- La revisión de imágenes ofrece **Aprobar y materializar coincidencias exactas**: una sola
  confirmación humana vuelve a contar hasta 500 candidatos, registra cada decisión y copia cada
  archivo después de verificar su SHA-256. Ambigüedades y conflictos continúan en revisión manual.
- Cada release nuevo congela `image_item_count` y `missing_image_item_count`. La pantalla de
  catálogos muestra ambos conteos y deshabilita composición/exportación cuando el snapshot tiene
  cero imágenes. La exportación operativa también lo rechaza en servidor con una explicación
  accionable; un release inmutable antiguo debe sustituirse por una versión nueva.
- El snapshot editorial incorpora `piece_type` y `engine_types` derivados de la categoría y de las
  aplicaciones aprobadas. Vista previa, HTML, PDF, PPTX y Data Merge/InDesign priorizan referencia,
  tipo de pieza, aplicaciones y motor, manteniendo fuera precio, moneda, inventario y cantidades.
- Paso manual para comprobar los 221 objetos ya materializados: reiniciar el revisor, abrir
  **Catálogos**, crear una versión nueva (por ejemplo `2026.27.08-r2`), publicar y exportar. El
  release anterior conserva cero imágenes por diseño y no se modifica.
- Verificación automatizada: 246 pruebas pasan; 6 integraciones PostgreSQL se omiten sin contraseña.
- Ajuste posterior de composición: las fotografías usan encaje proporcional completo en vista
  previa, HTML, PDF, PowerPoint e InDesign. Las cajas pueden dejar espacio libre, pero nunca recortan
  ni deforman el producto; PowerPoint calcula además el centrado para formatos extremos.
- La biblioteca de exportaciones ya no enumera cientos de objetos `IMAGE`: conserva su trazabilidad
  en el manifiesto y los paquetes, pero presenta una sola fila con cantidad y peso total. El HTML
  digital usa carga diferida nativa y decodificación asíncrona para no descargar de inmediato todas
  las fotografías de un catálogo extenso.
- El compositor ofrece **HTML autónomo** como entregable opcional. Incrusta las copias aprobadas como
  URI `data:` Base64 dentro de un único `.html`, conserva el HTML ligero como opción predeterminada
  y advierte que la variante autónoma puede pesar mucho y cargar todas las imágenes al abrirse.
- El HTML autónomo no incrusta ya el archivo original completo: crea en memoria una copia JPEG de
  pantalla limitada a 1200×900 px y calidad 82, respetando orientación y proporción. El original
  aprobado permanece intacto; CSS mantiene la fotografía completa, centrada y sin recorte.

## Bloque 2026-08-27: perfiles de marca v1

- Migracion forward-only `0013` crea perfiles de marca inmutables con codigo, nombre, eslogan, URL publica y paleta de cuatro colores; cada alta conserva operador y motivo. La aplicacion solo recibe `SELECT, INSERT`, sin UPDATE/DELETE.
- NATSUKI queda sembrada con perfil rojo/negro compatible con la direccion visual investigada.
- Nueva pantalla `Marcas` en la consola v1.12 permite crear perfiles con selector visual, sesion local, mismo origen, CSRF y confirmacion explicita. La URL opcional exige HTTPS y no admite credenciales.
- Nuevo launcher `MIGRAR-PERFILES-MARCA.cmd`; tambien se incorporo 0013 a la reconstruccion del limpiador de importaciones.
- Pendiente del mismo bloque: seleccionar el perfil antes del apply, eliminar la constante NATSUKI, incorporar logos mediante ingreso seguro y propagar los colores guardados a preview, HTML, PDF, PPTX e InDesign.
- Verificacion: 233 pruebas pasan; 6 integraciones PostgreSQL se omiten sin credenciales.
- Identidad NATSUKI confirmada para la siguiente iteracion: Barlow Condensed en titulares, DM Sans en cuerpo, ficha T1 a 12 pt con interlineado 1.8; logo de esquina y marca de agua opcional al 4-7%. Las fuentes no estan en el repositorio y no deben simularse ni descargarse sin validar los activos autorizados.
- Logo SVG maestro de NATSUKI incorporado desde `Z:\DOC MURILLO\logo nat.svg` sin modificar el original. Regla actualizada: 12 pt es minimo absoluto para todos los textos.
- Fuentes autorizadas recibidas e incorporadas con licencias OFL: Barlow Condensed Regular/Bold y DM Sans Regular/Bold. El PDF real ya registra y usa Barlow Condensed Bold en titulos, DM Sans en cuerpo y 12 pt/21.6 pt como minimo de cuerpo, referencias, metadatos y pies.

## Bloque 2026-08-27: PDF editorial v2

- Rediseñada la salida PDF con portada temática, edición, conteo e identidad del release; secciones
  numeradas; jerarquía propia para referencia, producto y datos técnicos; imágenes escaladas según
  densidad; encabezado, checksum abreviado, pie y numeración.
- La composición conserva temas y agrupación, muestra aplicaciones/OEM y sigue excluyendo campos
  comerciales y operativos. Continúa siendo prueba reproducible; PDF/X-4 final queda en InDesign.
- Verificación visual real: portada y página de fichas renderizadas a PNG sin cortes, solapamientos ni
  problemas de margen. Consola v1.11. Suite: 226 pruebas correctas, 6 integraciones omitidas sin clave.

## Bloque 2026-08-27: validación de imágenes por lote

- Consola operador v1.10 añade aprobación/rechazo atómico de hasta 500 asociaciones imagen–referencia
  pendientes. Reconsulta y bloquea el conjunto completo, compara el conteo esperado y conserva el
  hash individual de cada candidato en su decisión; cualquier cambio revierte todo el lote.
- La interfaz muestra el conteo pendiente y exige motivo más confirmación específica para aprobar o
  rechazar. La revisión individual permanece disponible para excepciones.
- El lote sólo decide asociaciones: no extrae, materializa ni publica fotografías.
- Suite: 226 pruebas correctas, 6 integraciones PostgreSQL omitidas sin contraseña.

## Bloque 2026-08-27: aplicaciones vehiculares de extremo a extremo

- Corregido el corte principal: `name_enrichment` ya no se pierde al aplicar. Los planes nuevos
  materializan fabricante, modelo y candidato de aplicación con años, posición, motores, confianza,
  regla y evidencia original; una marca no reconocida permanece vacía.
- La decisión de identidad resuelve atómicamente sus candidatos vehiculares visibles. Aprobar también
  aprueba el vocabulario pendiente utilizado; rechazar conserva el vocabulario y rechaza sólo las
  asociaciones del producto. La aprobación por filtro sigue limitada a 500 y audita cada identidad.
- Los releases incluyen `vehicle_makes`, `application_details` y etiquetas legibles. Vista previa,
  HTML, PDF, PPTX y Data Merge/InDesign muestran aplicaciones y permiten filtrar, agrupar o
  subagrupar por marca vehicular; productos multimarca aparecen en cada grupo correspondiente.
- El dry-run ahora ofrece **Verificar y preparar**: una confirmación ejecuta aprobación y aplicación
  como dos eventos dentro de una transacción. Publicar permanece separado.
- Añadida migración forward-only `0012` y `MIGRAR-APLICACIONES-VEHICULARES.cmd`. Debe aplicarse una vez
  en `perfect_catalog_dev` antes de probar un ingreso nuevo; requiere contraseña de `postgres`.
- Consola operador v1.9. Suite: 223 pruebas correctas, 6 integraciones PostgreSQL omitidas sin clave.

### Verificación manual pendiente

1. Ejecutar `MIGRAR-APLICACIONES-VEHICULARES.cmd` y confirmar `Resultado de psql: 0`.
2. Crear un dry-run nuevo; los planes ya aplicados antes de `0012` no contienen esos candidatos.
3. Abrir la cola, comprobar marca/modelo/años/motores y aprobar el filtro; construir un release nuevo.
4. Agrupar la vista previa por **Marca vehicular** y comparar varias referencias contra Odoo.

## Bloque 2026-08-27: inicio rápido y dirección visual

- Consola operador v1.8: `INICIAR-REVISOR.cmd` solicita únicamente la contraseña de PostgreSQL.
  Toma el usuario de Windows como actor, genera un código temporal de 72 bits, lo muestra sólo en
  consola y abre automáticamente `/operator/login` en el navegador predeterminado. No guarda
  credenciales ni coloca secretos en la URL; siguen disponibles los prompts manuales por CLI.
- Navegación reorganizada alrededor del flujo **Ingresar → Validar → Diseñar → Entregar**, conservando
  los accesos funcionales existentes, la sesión local, CSRF, cookies HttpOnly y auditoría.
- Catálogo digital HTML refinado con portada editorial, mejor espaciado, tarjetas, jerarquía de
  metadatos y comportamiento móvil, sin fuentes remotas ni JavaScript obligatorio.
- Añadido `docs/VISUAL_SYSTEM.md` con reglas compartidas para web/PDF/InDesign y referencias oficiales
  de Adobe para Data Merge, preflight, empaquetado, Output Preview y PDF/X-4. El perfil CMYK, sangrado
  y marcas quedan sujetos a la especificación real de la imprenta.
- Verificación: 219 pruebas pasan; 6 pruebas de integración PostgreSQL se omiten sin credenciales.

### Siguiente bloque recomendado

1. Crear presets visuales completos por marca y una previsualización comparativa T4/T2/T1/TABLE.
2. Añadir perfil de preflight de imprenta configurable y validar una exportación en Acrobat/InDesign.
3. Reducir pasos repetitivos dentro de la consola con un tablero de “continuar donde quedaste”.

## Sesión actual: Estudio visual de catálogos (2026-08-26)

### Resultado de esta sesión

- Alcance comercial simplificado por decisión del usuario: moneda, precios, inventario, UoM,
  responsable, etiquetas, favoritos, fechas operativas y `Imagen 128` quedan sólo en el XLSX/hash de
  origen. Nuevos dry-runs no los normalizan ni crean snapshots/medios; releases nuevos fijan esos
  campos a nulo y API v1.2, web y adaptadores de exportación los excluyen incluso al leer releases
  históricos. Las imágenes continúan únicamente por el workflow separado de originales aprobados.
- Parser vehicular v2 calibrado de forma agregada contra las muestras locales Perfect (896 filas) y
  PDM (154), sin copiar datos reales al repositorio. Añade perfiles de fuente, marcas/abreviaturas,
  años validados, cilindrada/códigos de motor con confianza diferenciada, posiciones canónicas, FMSI,
  referencias adicionales y corchetes PDM prudentes. El importador Natsuki incluye `name_enrichment`
  pendiente dentro de cada plan/fingerprint, pero apply/publicación aún no materializan inferencias.
  Las cantidades alternativas de PDM se ignoran deliberadamente según decisión del usuario.
- Consola operador v1.7 permite aprobar o rechazar en una sola transacción hasta 500 identidades
  pendientes del filtro actual. Exige motivo y confirmación específica, vuelve a consultar el conjunto,
  compara el conteo esperado y recalcula cada `review_sha256`; ante cualquier cambio revierte todo.
  Cada identidad conserva su propio evento de auditoría. El filtro desactiva restauración automática
  del navegador para que el selector visible corresponda a la consulta enviada.
- Consola operador v1.6 elimina el callejón sin salida posterior al dry-run: el enlace de Ingresos
  abre una inspección del UUID, alcance, versiones, hashes y fingerprint. Desde allí se puede aprobar
  y, en un segundo formulario explícito, aplicar el plan. Ambas transiciones conservan sesión local,
  CSRF, validación de origen, actor, motivo, confirmación y verificación criptográfica; aplicar sólo
  crea productos pendientes y conduce a la revisión individual.
- Nueva navegación `Catálogos` en la consola operador con listado de planes, releases y entregables.
- Construcción individual de borradores y publicación por checksum exacto desde formularios con sesión,
  Origin, CSRF, confirmación y actor derivado de la sesión; no existen acciones masivas.
- Configuración visual de título, subtítulo, agrupación, 1-3 columnas y formatos PDF/PPTX/InDesign JSON.
- Cada ejecución recibe UUID y directorio generado por el servidor. Las descargas autenticadas sólo
  admiten archivos enumerados por el manifiesto; rutas y nombres arbitrarios quedan rechazados.
- Historial local de exportaciones reconstruido desde manifiestos, sin depender de estado mutable web.
- Vista previa editorial de sólo lectura con agrupación y 1-3 columnas; valida el checksum completo,
  calcula conteos globales y limita el HTML a 24 fichas para escala de 25,000+ referencias.

### Pendiente siguiente

1. Reiniciar el revisor y probar la pantalla con un plan/release empresarial real.
2. Añadir filtros/agrupaciones multinivel y selección manual de productos.
3. Diseñar adaptadores de plantilla InDesign T4/T2/T1/TABLE/SEPARATOR y reporte de preflight.

### Avance InDesign del bloque

- Selector de perfil T4/T2/T1/TABLE incorporado al snapshot y a consola/CLI; valores desconocidos
  se rechazan antes de escribir archivos.
- El JSX crea páginas SEPARATOR por cambio de grupo, compone la densidad elegida y conserva perfil,
  release y checksum como etiquetas del INDD.
- Rutas de imagen sólo se aceptan relativas y sin `..`; se enlazan sin modificar el original.
- Cada INDD produce `perfect-catalog.indesign-preflight.v1` con imágenes faltantes, overflows y fuentes.
- Selección derivada por campo/texto y agrupación primaria/secundaria añadidas a preview, PDF, PPTX
  e InDesign; el manifiesto conserva conteo fuente, conteo seleccionado y criterios exactos.
- La consola de Ingresos permite indexar un ZIP de imágenes aceptado mediante POST individual con
  sesión/Origin/CSRF/motivo/confirmación. Muestra conteo, ambigüedades y hash; no extrae ni asocia.
- Preparada migración `0010` y núcleo `exact-approved-reference-v1`: candidatos deterministas por
  referencia primaria aprobada y decisiones humanas append-only con evidencia SHA-256 separada.
- Migración `0010` aplicada correctamente en `perfect_catalog_dev`; launcher
  `MIGRAR-REVISION-IMAGENES.cmd` conservado para otras instalaciones.
- Nueva cola `Imágenes`: generación exacta desde un índice concreto y aprobación/rechazo individual
  con sesión, Origin, CSRF, confirmación, motivo y hash de evidencia.
- Migración `0011` aplicada correctamente: materialización append-only e idempotente de decisiones
  aprobadas, con nueva verificación de ZIP, miembro, CRC, tamaño y SHA-256 antes de copiar.
- Las copias aprobadas se guardan content-addressed en `data/images/objects`; el ZIP de cuarentena
  permanece intacto y la aplicación no recibe permisos UPDATE/DELETE sobre la evidencia.
- Los releases nuevos capturan la imagen aprobada sin mutar releases anteriores. Cada exportación
  verifica de nuevo el SHA-256, empaqueta una copia autocontenida, la incluye en el manifiesto y
  entrega una ruta relativa segura al adaptador InDesign.
- PDF y PPTX colocan la copia empaquetada dentro de la ficha de producto. Una imagen que no pueda
  decodificarse degrada a ficha textual y no impide producir los demás entregables.
- La vista previa editorial muestra imágenes aprobadas mediante una ruta autenticada que vuelve a
  validar release, pertenencia, confinamiento de ruta y SHA-256 antes de servir cada archivo.
- La exportación permite seleccionar manualmente hasta 5.000 referencias exactas desde la consola
  o mediante `--reference` repetible en CLI. Se combina por intersección con el filtro opcional,
  rechaza referencias inexistentes y evita que un error tipográfico produzca un catálogo incompleto.
- El manifiesto y el snapshot InDesign conservan la lista canónica seleccionada; el manifiesto añade
  además su SHA-256 y el conteo exacto, de modo que la edición puede auditarse y reproducirse.
- Nuevo entregable `html`: catálogo digital responsive, portable y sin JavaScript, generado desde las
  mismas filas verificadas. Incluye portada, agrupaciones, 1-3 columnas, imágenes empaquetadas,
  versión y checksum del release, con escape estricto del texto procedente del snapshot.
- El HTML se selecciona desde la consola o con `--format html`, figura en el manifiesto SHA-256 y se
  descarga únicamente mediante la ruta autenticada ya limitada a archivos del manifiesto.
- Cada edición HTML produce además un `.digital.zip` determinista con `index.html` y todas sus
  imágenes verificadas. El ZIP figura como entregable separado con bytes y SHA-256, permitiendo
  trasladar o publicar el catálogo completo sin descargar assets uno por uno.
- Cuatro temas editoriales controlados (`forest`, `industrial`, `midnight`, `classic`) aplican una
  paleta consistente a HTML, PDF y PPTX; el valor también viaja en el layout InDesign.
- El manifiesto conserva ahora el layout completo (tema, títulos, agrupación, columnas y plantilla),
  además de selección y checksums; historiales anteriores sin layout siguen siendo compatibles.
- La vista previa editorial permite alternar los cuatro temas antes de exportar. Sólo acepta clases
  predefinidas servidas por el CSS local, por lo que no introduce estilos arbitrarios ni relaja CSP.
- Catálogo público renovado con tarjetas responsive de tres/dos/una columna, navegación por hasta 30
  categorías reales, búsqueda conservada al filtrar, marca, existencias e indicador visual de imagen.
- Las imágenes aprobadas del release se sirven en `/media/{product_id}` sólo después de revalidar
  pertenencia del producto, confinamiento bajo `data/images` y SHA-256. La ficha muestra además
  aplicaciones y referencias OEM con escape HTML.
- Nuevo `INICIAR-CATALOGO-PUBLICADO.cmd`: solicita la contraseña oculta y abre exclusivamente el
  último release publicado de NATSUKI; `INICIAR-SERVER.cmd` permanece como visor explícito del piloto.
- Verificación visual real completada en navegador integrado sobre los 893 productos del piloto XLSX:
  cuadrícula de escritorio, filtro `EMPAQUES / CARTER` con 15 resultados y breakpoint móvil de 390 px
  sin desbordamiento horizontal. El servidor temporal de prueba fue detenido al finalizar.
- La vitrina pública pagina en bloques de 48 productos: consulta sólo 49 filas para detectar si existe
  una página siguiente, conserva búsqueda/categoría en ambos sentidos y valida `page` entre 1 y 10000.
- Suite local actual: 201 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.
- Cada solicitud de `indesign-json` produce además un `.indesign.zip` determinista con
  `catalog.indesign.json`, imágenes verificadas, `ImportPerfectCatalog.jsx` e instrucciones.
- El JSX detecta automáticamente el snapshot adyacente al ejecutarse desde el paquete; si está
  instalado en el panel de Scripts conserva el selector de archivo. InDesign sigue sin acceder a BD.
- InDesign aplica ahora los cuatro temas editoriales permitidos mediante muestras RGB internas a
  portada, separadores, marcos de imagen, fichas y TABLE. Tema desconocido se rechaza.
- El INDD conserva `perfect_catalog_theme`; el preflight añade tema y conteos de grupos/páginas,
  además de imágenes faltantes, desbordamientos y fuentes no disponibles.
- Nuevo `verify-catalog-export MANIFEST`: validación offline sin contraseña que exige coincidencia
  exacta de directorio, bytes y hashes; inspecciona ZIP digital/InDesign, rutas, cifrado, tamaño
  descomprimido, archivos requeridos e imágenes. Devuelve `perfect-catalog.export-verification.v1`.
- PDF aplica el tema a jerarquía de portada y encabezados, añade regla editorial, versión, checksum
  abreviado y número de página. PPTX aplica la paleta a portada, fondos, títulos, subtítulo y fichas.
- QA visual real del PDF industrial completado en el visor integrado: portada de dos páginas sin
  recortes, título/subtítulo centrados, color temático, márgenes y pie legibles. Artefacto QA eliminado.
- Toda exportación InDesign genera además `*.datamerge.csv` y lo incluye como
  `catalog.datamerge.csv` en el paquete. Usa UTF-8 BOM, quoting CSV, listas unidas con `;`, campo
  relativo `@image` y neutralización de fórmulas para apertura segura en hojas de cálculo.
- La construcción de cualquier bundle ejecuta automáticamente `verify_catalog_bundle` después de
  escribir el manifiesto. Sólo retorna/mueve la exportación si archivos, hashes, ZIP e imágenes dan
  estado `verified`; CLI y operador reciben esa evidencia en el resultado.
- Cada descarga autenticada vuelve a comprobar que release, tamaño y SHA-256 coincidan con el
  manifiesto. Descargar el propio manifiesto verifica antes el bundle completo, incluidos sus ZIP.
- La pantalla Catálogos incorpora un tablero de producción en tres etapas —fuente, composición y
  biblioteca— con métricas de versiones, publicaciones y ediciones, más estados visuales de integridad.
- El compositor se divide en estructura, dirección visual y entregables. Temas, densidad y perfiles
  InDesign usan tarjetas radio nativas, accesibles y compatibles con CSP estricta sin JavaScript.
- El lanzador de vista previa rápida permite escoger categoría, densidad y tema; la página de control
  conserva después filtros y subagrupación, evitando previsualizar Bosque por error antes de exportar.
- Preview, HTML, PDF, PPTX e InDesign muestran ahora el mismo núcleo comercial cuando está disponible:
  referencia, nombre, categoría, marca, OEM y aplicaciones; los datos ausentes degradan sin inventarse.
- La vista previa alterna entre destino digital e InDesign y representa T4, T2, T1 y TABLE con
  densidades diferenciadas. Destino/perfil usan listas cerradas y los valores desconocidos devuelven 400.
- El preview InDesign representa portada y separadores y calcula páginas con la misma regla del JSX:
  una portada + un separador por grupo + `ceil(productos/capacidad)` reiniciado en cada grupo.
- Capacidades auditables: T4=4, T2=2, T1=1 y TABLE=16. Prueba Uvicorn/navegador: 12 productos,
  un grupo y TABLE mostraron correctamente 3 páginas estimadas.
- La biblioteca permite devolver el `*.preflight.json` generado por InDesign mediante carga individual
  con sesión, Origin, CSRF, confirmación y motivo. Límite 1 MiB y contrato JSON exacto.
- Antes de registrar, revalida todo el bundle y exige coincidencia de release, checksum, perfil, tema y
  productos. El recibo append-only queda fuera del bundle e incluye actor, fecha y SHA-256 del reporte.
- La consola muestra el último resultado: páginas, imágenes faltantes, overflows y fuentes. La prueba
  HTTP multipart real comprobó rechazo sin Origin y aceptación/redirección/estado con evidencia válida.
- Preview acepta título, subtítulo y hasta 5.000 referencias manuales exactas bajo el mismo contrato de
  exportación: normaliza duplicados, combina por intersección con filtros, conserva SHA-256 y rechaza
  cualquier referencia inexistente. La portada refleja esos valores antes de producir archivos.
- El compositor ofrece preview digital/InDesign de la configuración actual mediante JS externo self-only.
  Copia una allowlist de campos editoriales; nunca incluye CSRF, confirmación ni opciones mutantes. Sin JS,
  el launcher GET básico y el POST de exportación continúan operativos.
- El receptor de preflight deriva grupos y páginas desde el snapshot InDesign verificado y exige igualdad
  exacta con `group_count`/`page_count`; no acepta sólo conteos plausibles. Clasifica `passed` o `issues`.
- La biblioteca distingue `Sin incidencias`/`Con incidencias` y permite descargar el recibo JSON mediante
  una ruta autenticada limitada a UUID de release, exportación y recibo. UUID ajeno devuelve 404.
- El JSX deja de heredar preferencias del puesto: fija A4 vertical, puntos, origen por página, páginas no
  enfrentadas y sangrado uniforme de 3 mm antes de crear marcos. El INDD conserva formato/sangrado en labels.
- Corregido el fallo real de `Promover a dry-run`: una transacción SERIALIZABLE permanecía abierta mientras
  otra conexión creaba el plan, por lo que el snapshot inicial no podía verlo al insertar la FK de `0008`.
- La exclusión usa ahora advisory lock de sesión en una conexión autocommit; la lectura termina antes del
  dry-run y la escritura final abre un snapshot nuevo. Fallos inesperados muestran/loguean un ID correlacionado
  de 8 hex sin exponer el texto crudo de la excepción.
- Suite local actual: 217 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

## Sesión actual: Login estable y primer flujo de catálogo/InDesign (2026-08-26)

### Resultado de esta sesión

- Login operador corregido para Edge, Chrome y clientes integrados: cookie de challenge con alcance
  `/operator`, parseo estricto, compatibilidad segura Origin/Referer+Sec-Fetch-Site y diagnósticos
  separados para origen, challenge, código y límite de intentos, sin revelar ni registrar el código.
- Prueba HTTP real levanta Uvicorn en `127.0.0.1` y valida GET, cookie HttpOnly, CSRF, POST y redirección
  303 a `/operator`. El flujo TCP fue verificado; no había navegador integrado conectado para una
  comprobación visual automatizada.
- Añadido restablecimiento interactivo de contraseña para `perfect_catalog_app` mediante
  `RESTABLECER-CONTRASENA-REVISOR.cmd`; no conserva credenciales en archivos, argumentos o variables.
- Nuevo `export-catalog`: sólo acepta releases `published`, revalida todos sus hashes y genera PDF,
  PPTX, snapshot `perfect-catalog.indesign-snapshot.v1` y manifiesto SHA-256 sin sobrescribir destinos.
- Primer puente InDesign en `indesign/ImportPerfectCatalog.jsx`: abre el snapshot, valida publicación,
  crea portada y fichas editables, conserva UUID/checksum dentro del INDD y reporta desbordamientos.
- `0008` y `0009` aplicadas en `perfect_catalog_dev`. `0008` quedó reanudable y valida una tabla
  preexistente antes de completar índice, trigger y permisos; su lanzador conserva diagnóstico seguro.
- Verificación manual completada en Edge/Chrome local: el código temporal redirige a `/operator`.
  `Referrer-Policy: same-origin` permite el fallback Chromium sin divulgar referentes a otros orígenes.
- Suite local: 174 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Ejecutar las 6 integraciones PostgreSQL opt-in ahora que el esquema local está actualizado.
2. Probar un release empresarial publicado con `export-catalog` y abrir el JSON generado en InDesign.
3. Sustituir la maqueta básica JSX por adaptadores de plantilla T4, T2, T1, TABLE y SEPARATOR, con
   resolución revisada de imágenes/fuentes y reporte persistente de preflight.

## Sesión Actual: Índice no destructivo de imágenes (2026-08-26)

### Resultado de esta sesión

- Añadido `index-images` para submissions `image_archive` aceptados: exige actor, motivo y contraseña,
  y revalida ruta, tamaño y SHA-256 antes y después de recorrer el ZIP.
- El índice lee cada imagen por streaming sin extraerla y conserva ruta, MIME, tamaños, CRC32,
  SHA-256 de contenido y clave normalizada de búsqueda.
- Colisiones de nombre quedan `ambiguous`; entradas únicas permanecen `unmatched`. No existe matching
  automático ni escrituras en `media_asset`, `product_media` o productos.
- Migración forward-only `0009` crea cabecera/entradas append-only, contexto exacto submission/asset/hash
  y permisos mínimos `SELECT`/`INSERT`; launcher `MIGRAR-INDICE-IMAGENES.cmd` añadido.
- Suite local: 164 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Aplicar `0008` y `0009` en orden y ejecutar integraciones reales con fixtures sintéticos.
2. Exponer la indexación como POST individual en la consola operador, sin acción masiva.
3. Diseñar candidatos de asociación imagen-producto separados, siempre pendientes de revisión humana.
4. Añadir solicitud operador para exportar PDF/PPTX desde releases publicados.

## Sesión Actual: Promoción individual en consola operador (2026-08-26)

### Resultado de esta sesión

- Consola operador v1.2 muestra promociones existentes y ofrece `Promover a dry-run` sólo para
  submissions Odoo aceptados que todavía no tengan un plan enlazado.
- Nueva ruta exclusivamente POST individual con sesión, Origin, CSRF, campos exactos, motivo de
  4-500 caracteres y confirmación. No existe GET mutante ni acción masiva.
- El gateway conserva la contraseña sólo en memoria y ejecuta perfilado/dry-run fuera del event loop;
  el actor procede de la sesión firmada, no del formulario.
- El historial enlaza el plan creado y comunica que permanece pendiente de revisión.
- Suite local: 157 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

### Pendiente siguiente

1. Aplicar `0008` con `MIGRAR-PROMOCIONES.cmd` y probar la ruta con PostgreSQL real.
2. Construir el índice no destructivo de imágenes sobre ZIP validado en cuarentena.
3. Añadir una solicitud operador separada para exportar PDF/PPTX desde releases publicados.

## Sesión Actual: Promoción explícita de cuarentena (2026-08-26)

### Resultado de esta sesión

- Implementado `promote-intake` para datos Odoo aceptados: exige UUID, actor, motivo y contraseña;
  revalida ruta, tamaño y SHA-256 antes de copiar o procesar.
- Perfilado, sugerencias flexibles de columnas y dry-run quedan encadenados sólo por acción explícita.
  El resultado sigue en `awaiting_review`; no existe aprobación, apply o publicación automática.
- Migración forward-only `0008` añade evidencia append-only con relaciones exactas entre submission,
  asset/hash y batch/plan, más permisos `SELECT`/`INSERT` mínimos para la aplicación.
- Copia aislada y trazable bajo `data/intake/processing`; el objeto content-addressed original nunca
  se modifica. Promociones repetidas son idempotentes y las concurrentes usan advisory lock.
- Documentación operativa y launcher `MIGRAR-PROMOCIONES.cmd` añadidos.
- Suite local: 156 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas hasta aplicar `0008`.

### Pendiente siguiente

1. Aplicar `0008` en `perfect_catalog_dev` y ejecutar la integración real con un fixture sintético.
2. Exponer la promoción como POST individual en la consola operador, con CSRF, confirmación y motivo;
   no añadir acciones masivas.
3. Construir el índice no destructivo de imágenes sobre ZIP validado en cuarentena.

## Sesión Actual: Parser y exportaciones verificadas (2026-08-26)

### Resultado de esta sesión

- Portado selectivamente un parser puro de nombres y aplicaciones vehiculares; toda salida conserva
  procedencia/versionado y queda en `pending_review`, sin escrituras ni publicación automática.
- Añadida detección auxiliar de aliases de columnas, delimitadores y UTF-8/Windows-1252. No sustituye
  el contrato Odoo ni su validación de identidad y queda preparada para el futuro flujo explícito de
  promoción desde cuarentena.
- Añadido adaptador de exportación que revalida definición, snapshots, hashes individuales y hash
  agregado de un release antes de exponer filas a cualquier motor.
- Generadores PDF y PowerPoint desacoplados con portada, agrupaciones, branding básico, OEM,
  aplicaciones y diseños de 1-3 columnas. No consultan PostgreSQL ni datos empresariales.
- Dependencias fijadas: `reportlab==4.4.3` y `python-pptx==1.0.2`.
- Suite: 149 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas. Línea base anterior:
  143 aprobadas y las mismas 6 opt-in omitidas.

### Pendiente siguiente

1. Diseñar la promoción explícita desde cuarentena a perfilado/dry-run e integrar allí las
   sugerencias tabulares, sin importación automática.
2. Añadir una acción operador separada para solicitar exportaciones de releases publicados y una
   política de destino/nombres en `data/exports`; este bloque sólo aporta motores puros.
3. Ampliar el diccionario del parser únicamente con fixtures revisados y definir el workflow humano
   que convierte sugerencias en aplicaciones aprobadas.
4. Ejecutar las 6 integraciones opt-in al disponer de la contraseña local en el flujo protegido.

## Sesión Actual: Centro web de ingreso protegido (2026-08-24)

### Resultado de esta sesión

- Centro de ingreso añadido a `http://127.0.0.1:8081/operator/intake` dentro de la sesión operador;
  recibe Odoo XLSX/CSV/TSV, manual PDF y paquetes ZIP de imágenes o InDesign.
- Migración forward-only `0007`: `intake_asset` deduplica objetos por SHA-256 y
  `intake_submission` conserva cada evento; ambas tablas son append-only y el rol de aplicación
  sólo recibe `SELECT`/`INSERT`.
- Cuarentena local content-addressed en `data/intake`, excluida de Git; nombres recibidos nunca se
  convierten en rutas y una carga no ejecuta importación, extracción, apply ni publicación.
- Límites por tipo, `Content-Length`, multipart acotado, filename seguro, firma básica, SHA-256,
  ZIP traversal/enlaces/cifrado/expansión, ejecutables bloqueados y compensación ante fallo de BD.
- Historial paginado y filtrable con actor, motivo, hash, duplicados y causa de rechazo. Los bytes
  rechazados se borran; su evidencia permanece en PostgreSQL.
- `MIGRAR-INGRESOS.cmd` aplica `0007` y `docs/INTAKE_WORKFLOW.md` documenta operación, backup,
  alcance de cuarentena y la separación del procesamiento posterior.

- Consola Jinja2 separada implementada en `http://127.0.0.1:8081/operator`; el catálogo piloto de
  `INICIAR-SERVER.cmd` permanece intacto y de solo lectura en el puerto 8080.
- Nuevo `INICIAR-REVISOR.cmd`: solicita contraseña PostgreSQL, actor auditable y código temporal;
  valida la conexión antes de escuchar y nunca admite un host distinto de localhost.
- Cola set-based paginada (50 por página) con búsqueda, filtros y conteos; elimina el N+1 anterior
  y conserva el inspector CLI completo con su límite explícito de 5,000.
- Sesión en memoria de una hora, PBKDF2, límite de intentos, cookies firmadas HttpOnly/Strict, CSRF
  de login y sesión, validación Origin, formularios limitados, Jinja autoescape y CSP/no-store.
- Decisiones únicamente por POST individual con motivo; no existen GET mutantes, aprobación masiva,
  OpenAPI ni rutas de catálogo público en el proceso operador.
- Pruebas HTTP cubren autenticación, expiración, manipulación de cookie, CSRF, origen, XSS, cabeceras
  y separación de superficies. Integración real valida paginación/búsqueda como rol de aplicación.
- `VALIDAR-BLOQUE.cmd` permite repetir en una consola visible la suite PostgreSQL y el dry-run real
  sin escribir credenciales en argumentos, variables o archivos.

- Workflow `inspect-reviews` / `review-product` implementado para decisiones individuales con
  fingerprint del plan, `review_sha256` por ficha, actor y motivo obligatorios.
- Aprobación y rechazo actualizan atómicamente producto y referencia primaria; una decisión previa
  no puede sobrescribirse y el reintento idempotente exige el mismo hash guardado en auditoría.
- Migración forward-only `0006` aplicada: protege datos de identidad, limita UPDATE por columna y
  valida al final de la transacción que producto y referencia tengan estados coherentes.
- El constructor de releases ahora rechaza una marca completa si conserva identidades pendientes;
  ya no puede omitirlas silenciosamente y publicar un subconjunto accidental.
- La cola CLI tiene un límite explícito de 5,000 identidades; no trunca. La consola web ya pagina
  por consulta para la escala objetivo.
- `INICIAR-SERVER.cmd` abre el visor XLSX actual en `http://127.0.0.1:8080/`; todavía no presenta la
  cola PostgreSQL ni acciones de revisión.

- Auditoría provisional documentada en `docs/STATUS_AUDIT_V2_2.md`.
- Bloqueo exacto: no se recibió `Manual_Desde_Cero_Perfect_Trading_Natsuki_v2.2.pdf`; solo llegó
  el texto del encargo. La conformidad literal con el manual no puede cerrarse hasta adjuntarlo.
- API FastAPI v1.2 de solo lectura implementada sin retirar el visor existente.
- El origen predeterminado es el último `catalog_release` publicado de una marca; búsqueda,
  categorías y detalle permanecen encerrados en ese release.
- Las URLs y respuestas publicadas usan UUID estable de variante o template. Los IDs
  `source-row:*` quedan limitados y rotulados como modo piloto XLSX explícito.
- Cada snapshot valida schema, identidad y hash canónico; el hash agregado valida marca, versión,
  orden e inventario completo de items antes de servir cualquier consulta.
- Workflow `build-release` / `inspect-release` / `publish-release` / `archive-release` implementado
  con actor, motivo, fingerprint/checksum exactos, transacciones serializables e idempotencia.
- La construcción exige plan aplicado, productos activos y una referencia interna primaria
  aprobada por identidad; aplicar datos nunca activa ni publica automáticamente.
- `catalog-release-v2` compromete criptográficamente también la definición y selección del release.
- La migración forward-only `0005` fue aplicada: triggers protegen releases, items y auditoría como
  append-only; solo permiten `draft → published → archived` y permisos mínimos por columna.
- `perfect-catalog-api` arranca el origen publicado por defecto. `INICIAR-SERVER.cmd` conserva el
  piloto local al pasar explícitamente `--source-dir data\imports`.
- Empaquetado corregido: `tools.odoo_profiler` funciona fuera de la raíz del repositorio.
- `.env.example` corregido para no presentar SQLite como base de desarrollo.
- Prueba de humo real: XLSX maestro de 893 filas, API devuelve catálogo y fichas correctamente.
- Contrato/importador v0.2: ya no exige 893 filas ni 13 columnas en orden exacto; acepta
  reordenamiento, conserva columnas nuevas y reporta opcionales ausentes, con límite de piloto.
- Segunda muestra real verificada: 237 filas y solo 2 columnas críticas, sin inventar opcionales.
- Workflow `approve-plan` / `apply-plan` implementado con actor, motivo y fingerprint obligatorios.
- El apply recalcula hashes, verifica el archivo, bloquea el plan y usa una transacción serializable;
  un segundo intento sobre un plan aplicado responde `already_applied` sin repetir escrituras.
- Alcance seguro actual: altas, snapshots completos, `no_change` y medios marcados pendientes. Las
  operaciones `update`, `blocked` y `conflict` se rechazan antes de escribir.
- `0003` fue aplicada en `perfect_catalog_dev`; flexibiliza el conteo opcional de variantes y limita
  por columna las transiciones permitidas al rol de aplicación.
- `0004` fue creada y aplicada forward-only para corregir drift de lectura con mínimo privilegio:
  `perfect_catalog_app` recibe SELECT solo en las 18 tablas que consume actualmente.
- Integración real como `perfect_catalog_app`: aprobación, alta, snapshot con -2/0, auditoría,
  reintento `already_applied`, permisos y rollback transaccional verificados.
- Integración del read model como `perfect_catalog_app`: selección, búsqueda, categorías, ficha por
  UUID y detección de manipulación, todo con datos sintéticos y rollback.
- Integración completa como rol real: apply sintético, activación/revisión sintética, build,
  checksum erróneo, publicación, lectura UUID, archivo, reintentos e inmutabilidad con rollback.
- Pruebas: 143 descubiertas y 143 aprobadas, incluidas las 6 integraciones PostgreSQL.
- Dry-run real v0.3 repetido: 893 filas, 2,497 items, archivo intacto y 0 escrituras empresariales.
- Ningún plan real fue aprobado/aplicado ni se publicó un release empresarial; no se modificó Odoo
  ni el Excel fuente y las ocho tablas empresariales siguen vacías.

### Próxima etapa por dependencias

1. Añadir una promoción explícita desde cuarentena hacia perfilado/dry-run; la recepción nunca debe
   importar automáticamente.
2. Construir el índice no destructivo de imágenes sobre un ZIP de cuarentena validado.
3. Añadir reconciliación `update` campo por campo cuando una exportación completa aporte identidad
   Odoo estable; hasta entonces permanece bloqueada por diseño.
4. Continuar con catálogo enriquecido y PWA/offline sobre releases inmutables.

### Sesión anterior: Inicialización del Proyecto (2026-08-17)

### Estado de Cumplimiento ✓

- ✓ Diagnóstico del entorno completado
- ✓ Repositorio Git inicializado
- ✓ Documentación base creada
- ✓ Estructura de carpetas planificada
- ✓ Reglas no negociables documentadas
- ✓ Muestra real de Odoo analizada preliminarmente
- ✓ Schema y migración validados en PostgreSQL
- ✓ Dry-run de Natsuki ejecutado sin escrituras empresariales
- ✓ MVP web local de consulta sobre la muestra funcionando
- ✓ Visor local detecta automáticamente el XLSX más reciente en `data/imports`
- ✓ Ficha individual web y ficha imprimible funcionando

### Completado en Esta Sesión

1. **Diagnóstico de Entorno**
   - Windows 11 Pro (Build 26200) - 64 bits
   - 237.41 GB libres en C:\
   - VS Code 1.133.0
   - Git 2.54.0
   - Python 3.14.5 disponible
   - Adobe InDesign 2026 presente
   - PostgreSQL y pgAdmin: NO instalados (fase posterior)

2. **Inicialización de Repositorio**
   - git init ejecutado
   - .gitignore configurado
   - Archivos de documentación creados:
     - PROJECT.md
     - AGENTS.md
     - HANDOFF.md (este archivo)
     - README.md
     - .env.example

3. **Documentación y validación**
   - Reglas no negociables documentadas
   - Estructura organizativa: empresa, marcas, fuente maestra
   - Funcionalidades: búsqueda, filtrado, generación de catálogos
   - Formatos de salida: web, PDF, InDesign
   - `docs/DATA_SPEC.md`: perfil preliminar de la muestra de 893 filas
   - Plan de importación persistido en `awaiting_review`

### Próximos Pasos (Orden de Prioridad)

#### FASE 1: Análisis de Datos (PRELIMINAR COMPLETADO)
- [x] Analizar muestra real de Excel de Odoo (Natsuki / Empaques)
- [x] Analizar estructura de columnas y completitud
- [x] Documentar campos observados en DATA_SPEC.md
- [ ] Obtener exportación completa de Odoo para ampliar la evidencia
- [ ] Identificar relaciones OEM, cross-reference, FMSI y aplicaciones vehiculares
- [ ] Convertir la especificación preliminar en contrato definitivo tras recibir más exportaciones

**Responsable**: Analista de Datos / Odoo  
**Dependencias actuales**: Exportación completa y/o nuevas muestras de Odoo

#### FASE 2: Diseño y Validación de Base de Datos
- [x] Diseñar schema de PostgreSQL preliminar
- [x] Definir tablas, relaciones, constraints e índices
- [x] Validar DDL y migración en PostgreSQL
- [ ] Revisar ajustes del schema contra la exportación completa

**Responsable**: Coordinador + Ingeniero Backend  
**Dependencias**: DATA_SPEC.md  
**Bloqueado por**: FASE 1  

#### FASE 3: Importador de Datos (Dry-run preliminar)
- [x] Importador Python para la muestra Excel/CSV
- [x] Validaciones, staging y resultados separados
- [x] Plan persistido con hash canónico y compuerta de aprobación
- [x] Control de imágenes sin decodificar ni modificar originales
- [ ] Ampliar reglas con la exportación completa de Odoo

**Responsable**: Ingeniero Backend  
**Dependencias**: Schema de BD  
**Bloqueado por**: FASE 2  

#### FASE 4: API Base
- [x] Búsqueda local por referencia y nombre
- [x] Filtro local por categoría
- [x] API HTTP formal con endpoints JSON
- [x] Read model publicado con UUID y checksum
- [ ] Endpoints de agrupación multinivel

**Responsable**: Ingeniero Backend  
**Dependencias**: BD con datos + Importador  
**Bloqueado por**: FASE 3  

#### FASE 5: Interfaz Web Local
- [x] Búsqueda por referencia y nombre
- [x] Filtro inicial por categoría
- [ ] Filtros multi-nivel
- [ ] Agrupación dinámica
- [x] Visualización de resultados de ficha básica

**Responsable**: Ingeniero Frontend  
**Dependencias**: API  
**Bloqueado por**: FASE 4  

#### FASE 6: Exportación de PDFs
- [ ] Generador de fichas PDF
- [ ] Compilación de catálogos PDF
- [ ] Metadatos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD con datos + API  
**Bloqueado por**: FASE 3  

#### FASE 7: Integración InDesign
- [ ] Scripts de InDesign
- [ ] Plantillas T4, T2, T1, TABLE, SEPARATOR
- [ ] Generación de documentos INDD
- [ ] Control de imágenes, fuentes, desbordamientos

**Responsable**: Especialista en Exportación  
**Dependencias**: BD + Exportación PDF  
**Bloqueado por**: FASE 6  

### NO Hacer Todavía

- ❌ Ejecutar APPLY sin revisión y aprobación humana explícita
- ❌ Tratar la muestra de 893 filas como el catálogo completo
- ❌ Declarar definitivo el contrato del importador con la evidencia actual
- ❌ Tocar fotografías originales
- ❌ Modificar el Excel maestro de muestra

### Decisiones de Arquitectura Cerradas

| Decisión | Estado | Definición |
|----------|--------|------------|
| Base de datos | Cerrada | PostgreSQL es la base oficial. SQLite no será la base principal y solo podría usarse para pruebas aisladas si fuera necesario. |
| Backend | Cerrada | FastAPI es el backend oficial. |
| Frontend inicial | Cerrada | Jinja2 + HTML + CSS + JavaScript. React no se utilizará inicialmente. |
| Evolución | Cerrada | La arquitectura podrá evolucionar hacia un frontend separado si una necesidad real lo justifica. |

El frontend inicial debe ofrecer una interfaz premium, responsive y moderna. La ausencia inicial de React reduce complejidad y no limita el diseño.

### Decisiones Pendientes

| Decisión | Estado | Notas |
|----------|--------|-------|
| Formato Snapshots InDesign: XML vs JSON | Pendiente | Definir tras primer análisis de datos |
| Control de Versiones de Catálogos | Parcialmente cerrada | Releases inmutables, versionados y con checksum; falta definir la política operativa de publicación y retención. |

### Notas Técnicas

- Ruta del proyecto: `C:\PERFECT_CATALOG`
- MVP local: `http://127.0.0.1:8080`
- Lanzamiento: `INICIAR-SERVER.cmd` o `scripts/run_catalog_web.py`
- El MVP lee el Excel de muestra en modo solo lectura; no requiere contraseña ni conexión a PostgreSQL
- Al copiar una nueva exportación `.xlsx` a `data/imports`, el visor la recarga automáticamente en la siguiente consulta
- Ficha web: `/producto/<fila>`; versión imprimible: `/producto/<fila>/ficha`
- La ficha imprimible se puede guardar como PDF desde el navegador; no genera aún un PDF automatizado
- Usuario propietario: AzureAD\Diseño2
- Política de ejecución PowerShell: Bypass
- No se ejecuta como administrador (OK, no requerido)

### Contactos y Escalaciones

- **Bloqueos con Excel**: Contactar a Área de Odoo
- **Decisiones estratégicas**: Revisar con Gerencia
- **Cambios en reglas de negocio**: Actualizar PROJECT.md inmediatamente

### Última Actualización

- **Fecha**: 2026-08-17
- **Sesión**: Inicialización
- **Duración**: ~1 hora diagnóstico + setup
- **Próxima Revisión**: Tras obtener Excel de Odoo

---

### Cómo Usar Este Archivo

1. **Al Iniciar Sesión**: Lee este archivo completo
2. **Identifica Bloqueadores**: Busca items con ❌ o "Pendiente"
3. **Continúa desde Último Checkpoint**: Busca checkboxes [ ] sin marcar
4. **Antes de Cerrar Sesión**: Actualiza este archivo con tu progreso
5. **Comenta Decisiones**: Explica el "por qué" no solo el "qué"
## 2026-08-27 - Limpieza guiada de importaciones

- Se agrego `LIMPIAR-IMPORTACIONES.cmd` para empezar de cero sin reinstalar PostgreSQL ni cambiar usuarios o contrasenas.
- La herramienta exige cerrar el revisor, escribir `LIMPIAR IMPORTACIONES` y proporcionar la contrasena de PostgreSQL una sola vez.
- Antes de limpiar crea un `pg_dump` y mueve `data/imports`, `data/intake`, `data/images` y `data/exports` a `data/backups/limpieza-<fecha>`; no borra respaldos anteriores.
- Reconstruye el esquema `perfect_catalog` y reaplica en orden las migraciones 0001-0012, eliminando importaciones y derivados sin dejar referencias huerfanas.
- La limpieza no se ejecuta durante desarrollo ni pruebas: solo se realiza al abrir voluntariamente el nuevo lanzador y confirmar.
- Verificacion real: la limpieza del 2026-08-27 creo un dump PostgreSQL valido de 138 MB y archivo 104 elementos (aprox. 275 MB) en `data/backups/limpieza-20260827-092235`; las cuatro carpetas activas quedaron vacias.
- Se corrigio el limpiador para conservar `.gitkeep` sin modificarlo en futuras ejecuciones.

## Proximo bloque acordado - Perfiles de marca y direccion visual

- La referencia visual objetivo admite portada de marca, cuadricula de productos y ficha individual para PDF/InDesign.
- La consola solo ofrece actualmente cuatro paletas fijas (`forest`, `industrial`, `midnight`, `classic`); todavia no guarda colores o logos por marca.
- Bloqueo funcional confirmado: `application.py` materializa altas nuevas con la constante `NATSUKI`. El campo Marca al construir un release resuelve una marca existente, no es un alta de marca.
- Implementar antes del siguiente catalogo multimarca: migracion de perfil de marca, pantalla `Marcas`, alta/edicion auditada de nombre/codigo/logo/eslogan/colores, seleccion de marca al preparar la importacion y propagacion exacta a PDF, HTML, PPTX e InDesign.
- Investigación visual y funcional documentada en `docs/DIRECCION-VISUAL-CATALOGOS.md`, con referencias de NSK, ZF, HELLA, Parker Racor, Brembo, TecDoc y Adobe InDesign.
- Sistema de páginas definido: portada P0, separador S, cuadrículas T4/T2, ficha T1 y guía técnica TABLE.

## 2026-08-27 - Marca vinculada y sistema editorial 1-4

- La migración `0014_brand_profile_workflow.sql` vincula cada plan y marca materializada con un perfil visual: tipografías, mínimo 12 pt, interlineado 1.8, logo de esquina y marca de agua configurable (4-7%).
- `MIGRAR-MARCA-CATALOGO.cmd` aplica el cambio en Windows y debe ejecutarse una vez antes de preparar una importación nueva.
- El dry-run exige elegir la marca. La selección se audita, se materializa y queda congelada en el release; las altas ya no usan una constante NATSUKI.
- PDF, HTML digital, PPTX e InDesign reciben el perfil inmutable. Natsuki usa su paleta, Barlow Condensed, DM Sans, logo oficial y marca de agua.
- Sistema: P0 portada, S separador automático, T4 (4 fichas), T2 (2), T1 (1) y TABLE (10 filas legibles a 12 pt). El ZIP InDesign incluye logo y `Document fonts`.
- QA visual: PDF Natsuki T2 renderizado a PNG e inspeccionado en portada y página de producto.
- Suite completa: 237 pruebas aprobadas y 6 omitidas de PostgreSQL opt-in.
- Corrección operativa: el lanzador 0014 detecta si falta `brand_profile`, aplica primero 0013 con la misma sesión de `psql` y omite de forma segura cualquiera de las dos migraciones que ya esté instalada.
- Corrección PostgreSQL: la restricción de `logo_asset_key` usa `[.]svg`, evitando el doble escape que rechazaba la ruta válida `brands/natsuki/logo.svg`; el intento fallido quedó revertido por la transacción.
- Corrección de inspección: la consulta del plan agrupa explícitamente el perfil de marca unido. El error anterior se mostraba incorrectamente como “PostgreSQL no disponible”; ahora se registra y presenta un identificador diagnóstico seguro.
- Diagnóstico de imágenes: las excepciones inesperadas al aprobar una asociación individual o un lote ahora se registran en la consola con un identificador seguro que también aparece en la pantalla; no se muestran referencias, hashes ni credenciales.
- Aprobación en lote de imágenes corregida: `FOR UPDATE` exigía un permiso incompatible con la tabla append-only. Se reemplazó por `pg_advisory_xact_lock` dentro de la transacción serializable; se conservan permisos mínimos y la comprobación del conjunto pendiente exacto.
- Auditoría preventiva de permisos: decisión individual y materialización tenían el mismo riesgo sobre evidencia append-only. Ambas usan ahora bloqueos advisory por candidato y no requieren ampliar permisos `UPDATE`.
- Construcción de release: los valores numéricos del perfil visual provenientes de PostgreSQL se convierten a JSON canónico antes de calcular y persistir el snapshot. Se evita que `Jsonb` rechace objetos `Decimal`; la ruta incluye diagnóstico seguro.

## 2026-08-27 - Operación simplificada y auditoría preventiva

- La carpeta raíz expone un solo actualizador: `ACTUALIZAR-SISTEMA.cmd`. Detecta y aplica en orden únicamente los bloques pendientes 0007–0015; si el esquema base no existe se detiene sin reconstruir ni borrar datos.
- Se retiraron los ocho lanzadores públicos `MIGRAR-*`. Los SQL históricos y bootstrap internos permanecen versionados para trazabilidad y reconstrucción controlada.
- Regla operativa: el usuario trabaja con `INICIAR-REVISOR.cmd`; ejecuta `ACTUALIZAR-SISTEMA.cmd` únicamente después de recibir código nuevo que cambie la base o cuando la consola indique que falta una actualización.
- Imágenes: la consola permite materializar en lote hasta 500 asociaciones aprobadas, verificando el conjunto exacto y cada SHA-256. Después debe construirse una versión nueva porque los releases anteriores son inmutables.

## 2026-08-27 - Identidad madre y activos visuales por marca

- La migración `0015_visual_identity_assets.sql` agrega revisiones append-only para dos alcances: empresa madre y marca de producto. Conserva nombre, cuatro colores, logo, SHA-256, operador, motivo y fecha.
- **Marcas** incluye un espacio para subir el logo y definir la paleta de Perfect Trading, además de controles equivalentes en cada tarjeta de marca. Las revisiones anteriores no se sobrescriben.
- La carga exige sesión, mismo origen, CSRF, confirmación y motivo; limita el logo a 5 MiB, acepta PNG/JPG/SVG y rechaza SVG con scripts, `foreignObject` o recursos externos.
- Los releases nuevos congelan las identidades madre y de producto. El empaquetador verifica ruta y SHA-256, incluye ambos logos en el bundle y los propaga a HTML, PDF, PPTX e InDesign según compatibilidad.
- Portada: Perfect Trading actúa como firma común y la marca de producto como marca de agua. Páginas interiores: la marca de producto mantiene el logo de esquina. SVG se conserva en HTML/InDesign; para presencia idéntica en PDF/PPTX se recomienda PNG/JPG.
- Operación: ejecutar una vez `ACTUALIZAR-SISTEMA.cmd`, entrar con `INICIAR-REVISOR.cmd`, abrir **Marcas**, guardar la identidad madre y después las marcas necesarias. Es obligatorio construir una versión nueva para incorporar los cambios.

## 2026-08-27 - Auditoría visual y accesibilidad 1.16

- La aplicación usa ahora una región `main` semántica real, avisos de resultado anunciables, blancos de confirmación de 24 px, foco visible en selectores visuales y respeto por `prefers-reduced-motion`.
- El HTML exportado incorpora un índice navegable por secciones, anclas estables y fichas semánticas `dl/dt/dd` para OEM, aplicaciones y motor. Las imágenes conservan `object-fit: contain` y carga diferida.
- El PDF incorpora metadatos de título, autor, asunto, creador, palabras clave y marcador de portada; conserva tipografía mínima de 12 pt, interlineado 1.8 y logos separados de empresa/marca.
- QA: HTML renderizado en Edge a 1440x1200 e inspeccionado sin recortes ni solapamientos. Edge headless no renderizó su visor PDF y Poppler no está instalado; la generación y estructura PDF sí quedaron cubiertas por pruebas automatizadas.
- Referencias aplicadas: WCAG 2.2 (foco, tamaño de objetivo, movimiento y estructura) y guías oficiales de Adobe sobre PDF etiquetado, orden de lectura, texto alternativo, metadatos, marcadores y compresión.
- Suite completa: 252 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.

## 2026-08-27 - Corrección definitiva de encaje de imágenes 1.16.1

- La imagen del HTML digital y autónomo ocupa una caja explícita al 100% y usa `object-fit: contain` con centrado; el navegador ya no puede resolver `auto/max-height` de forma que termine ocultando extremos.
- Se reprodujo el caso con una imagen horizontal de 1600x900 marcada en sus cuatro bordes y se renderizó localmente en Edge. El original y la copia optimizada conservan su relación de aspecto y no se recortan.
- Los HTML ya exportados no se modifican retroactivamente: es necesario generar un entregable nuevo para recibir el CSS 1.16.1.
- Suite completa: 252 pruebas aprobadas; 6 integraciones PostgreSQL opt-in omitidas.
