# Exportación de catálogos publicados

## Desde la consola visual

Con `INICIAR-REVISOR.cmd` activo, abre `http://127.0.0.1:8081/operator/catalogs`.
La pantalla permite, en orden:

1. construir un borrador inmutable desde un plan aplicado y completamente revisado;
2. revisar UUID/checksum y publicar individualmente el borrador;
3. abrir una vista previa HTML limitada, con agrupación y 1-3 columnas;
4. filtrar por texto/campo y organizar hasta dos niveles de agrupación;
5. elegir título, subtítulo, columnas, perfil InDesign y formatos;
6. generar y descargar HTML/ZIP digital, PDF, PPTX, snapshot/paquete InDesign y manifiesto.

El compositor presenta estas decisiones en tres etapas: estructura del contenido, dirección visual
y entregables. Los presets de tema, densidad y perfil InDesign son controles HTML nativos y funcionan
sin JavaScript; el servidor sigue validando cada valor contra listas cerradas.

La ficha base mantiene paridad semántica entre vista previa, HTML, PDF, PowerPoint e InDesign:
referencia, nombre, categoría, marca, referencias OEM y aplicaciones. Cada campo opcional sólo aparece
cuando pertenece al snapshot publicado; no se completan datos comerciales por inferencia.

En la vista previa, `Destino` alterna entre la cuadrícula digital configurable y una simulación de
InDesign. Esta última representa T4 en dos columnas, T2/T1 en fichas progresivamente amplias y TABLE
como filas compactas sin imagen. Es una prueba de composición; el JSX sigue siendo quien crea el INDD.

La vista previa vuelve a verificar el release completo, calcula el total de todos los grupos y
renderiza como máximo 24 fichas para mantener una respuesta ágil con catálogos grandes. No crea
archivos ni altera datos.

Los archivos quedan bajo `data/exports/catalogs/<release-uuid>/<export-uuid>/`. El navegador
no decide rutas y sólo puede descargar nombres incluidos en el manifiesto de esa exportación.
El manifiesto diferencia `source_item_count` del release y `selected_item_count`; el filtro nunca
modifica el release publicado.

## Desde línea de comandos

El comando `export-catalog` genera entregables únicamente desde un release con estado
`published`. Antes de escribir, vuelve a validar los hashes de cada producto y el checksum
global del release.

```powershell
perfect-catalog export-catalog RELEASE_UUID `
  --output-dir data/exports/catalogs/mi-catalogo `
  --title "Catálogo Natsuki" `
  --subtitle "Edición 2026" `
  --columns 2 `
  --prompt-password
```

Por defecto se generan:

- HTML responsive y `.digital.zip` portable con sus imágenes.
- PDF para distribución e impresión.
- PPTX editable para presentación digital.
- `*.indesign.json`, snapshot UTF-8 estable para InDesign.
- `*.datamerge.csv`, fuente UTF-8 BOM para Data Merge con campo de imagen `@image`.
- `*.indesign.zip`, paquete autocontenido con snapshot, imágenes, JSX e instrucciones.
- `*.manifest.json`, con release, versión, checksum fuente y SHA-256 de cada entregable.

PDF y PPTX comparten el tema seleccionado. El PDF imprime versión, checksum abreviado y numeración;
PowerPoint conserva esos datos en portada y aplica la paleta a fondos, encabezados y fichas.

Se puede repetir `--format pdf`, `--format pptx` o `--format indesign-json` para limitar
la salida. El directorio de destino debe estar vacío; el comando no reemplaza archivos.

## Verificar antes de distribuir

La verificación es offline y no solicita contraseña PostgreSQL:

```powershell
perfect-catalog verify-catalog-export `
  data/exports/catalogs/RELEASE_UUID/EXPORT_UUID/catalogo.manifest.json
```

Comprueba esquema/release, lista exacta del directorio, bytes y SHA-256 de cada entregable. También
abre los ZIP digital e InDesign, rechaza rutas inseguras, duplicadas o cifradas, limita el tamaño
descomprimido y vuelve a comprobar que todas las imágenes manifestadas estén dentro de cada paquete.
Un resultado válido devuelve `perfect-catalog.export-verification.v1` con estado `verified`.
La misma comprobación se ejecuta automáticamente antes de que una exportación nueva sea entregada
por CLI o movida desde el directorio temporal al historial de la consola operador.
La consola vuelve a validar tamaño y SHA-256 del entregable en cada descarga autenticada. Si se pide
el manifiesto, revalida el bundle completo; un archivo alterado después de su creación no se sirve.

## Contrato InDesign v1

El snapshot usa el esquema `perfect-catalog.indesign-snapshot.v1` e incluye:

- identidad, versión y checksum del release publicado;
- opciones neutrales de maquetación;
- productos ordenados exactamente como quedaron congelados en la publicación.

Este JSON es el límite entre datos y maquetación. El script implementa perfiles T4, T2, T1,
TABLE y páginas SEPARATOR sin consultar la base de datos directamente desde InDesign.

## Crear el primer INDD editable

1. Descarga y extrae completamente `*.indesign.zip`.
2. En InDesign, abre `Ventana > Utilidades > Scripts`.
3. Ejecuta el `ImportPerfectCatalog.jsx` extraído. Detectará automáticamente
   `catalog.indesign.json` en la misma carpeta; instalado separadamente conserva el selector manual.
4. Elige dónde guardar el `.indd`.

Como alternativa, abre `Ventana > Utilidades > Combinación de datos` y selecciona
`catalog.datamerge.csv`. Sus columnas son referencia, nombre, categoría, marca, aplicaciones, OEM e
imagen relativa. El CSV usa BOM UTF-8, conserva comas mediante quoting y neutraliza prefijos de
fórmula (`=`, `+`, `-`, `@`) en datos procedentes del snapshot.

El script v1 crea portada, separadores automáticos por grupo y páginas de producto según
el perfil seleccionado: T4, T2, T1 o TABLE. Guarda en las etiquetas del documento el UUID,
checksum, perfil y tema editorial del release. Los temas `forest`, `industrial`, `midnight` y
`classic` crean muestras RGB controladas y se aplican a portada, separadores, imágenes, fichas y
filas TABLE; cualquier tema desconocido detiene la importación. Si el snapshot contiene rutas relativas seguras de imágenes,
las coloca como enlaces sin modificar los originales.

Al guardar el INDD también crea `*.preflight.json` con tema, conteos de grupos/páginas, imágenes
ausentes, índices de fichas con texto desbordado y fuentes no disponibles. InDesign nunca se conecta directamente a
PostgreSQL.

Antes de asociar fotografías, los ZIP aceptados pueden indexarse desde `Operador > Ingresos`.
Esa acción sólo indexa nombres, rutas y hashes, y detecta colisiones. La cola `Imágenes` exige una
decisión humana individual y la materialización vuelve a verificar ZIP, miembro, CRC y SHA-256;
únicamente releases nuevos incorporan esas copias content-addressed.
