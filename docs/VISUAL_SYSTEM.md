# Sistema visual para web, PDF e InDesign

## Dirección

Perfect Catalog usa una misma jerarquía editorial en los tres canales: marca y edición, navegación
por familia, referencia como identificador principal, nombre del producto, aplicaciones y evidencia
técnica. Los temas cambian color y carácter, pero no alteran el orden de lectura ni el contenido.

La interfaz de operador organiza el trabajo en cuatro momentos visibles: **Ingresar**, **Validar**,
**Diseñar** y **Entregar**. La web pública y el HTML portable priorizan búsqueda y lectura responsive;
PDF e InDesign priorizan ritmo de página, consistencia y comprobaciones de producción.

## Reglas compartidas

- Variables de color y espaciado controladas; ningún texto importado puede inyectar estilos.
- Referencias en tipografía técnica y títulos en una serif editorial, con alternativas locales.
- Contraste, foco visible, etiquetas persistentes y controles utilizables con teclado.
- Imágenes aprobadas enlazadas por hash, sin modificar originales ni inventar sustitutos.
- T4, T2, T1, TABLE y SEPARATOR son composiciones del mismo modelo, no fuentes de datos distintas.
- Precio, moneda, cantidades, inventario y datos operativos de Odoo no forman parte del catálogo.

## Web y catálogo digital

- Cuadrícula adaptable de una a tres columnas y tarjetas que conservan la referencia visible.
- Navegación de operador breve y orientada al flujo, con estados vacíos que indiquen el siguiente paso.
- HTML portable sin dependencias remotas ni JavaScript obligatorio.
- La vista previa debe compartir tema, selección, agrupación y densidad con la exportación final.

## PDF para imprenta

- Salida base en PDF/X-4 cuando se prepare el arte final para imprenta.
- Perfil CMYK, sangrado y marcas se fijan según la especificación de la imprenta; no se presupone un
  perfil universal. La caja de corte y el sangrado deben comprobarse en Output Preview.
- Preflight previo a entrega: fuentes, enlaces, resolución efectiva, sobreimpresión, separaciones,
  cobertura de tinta, texto desbordado y cajas de página.
- El PDF generado directamente por el sistema sirve como prueba editorial reproducible; la salida
  final de alta producción puede componerse y certificarse desde InDesign.

## InDesign

- JSON versionado es la fuente canónica. El adaptador crea documento, páginas padre, estilos de
  párrafo/objeto y perfiles T4/T2/T1/TABLE/SEPARATOR sin consultar PostgreSQL.
- Data Merge es apropiado para plantillas repetitivas y pruebas; el JSX sigue siendo el adaptador
  controlado cuando hacen falta agrupación, separadores, paginación o evidencia técnica.
- Cada ejecución debe reportar enlaces ausentes, fuentes faltantes, texto desbordado y páginas
  creadas. Antes de entregar: ejecutar preflight y empaquetar INDD, enlaces, fuentes permitidas e
  informe.

## Referencias oficiales consultadas

- Adobe InDesign, Data Merge: https://helpx.adobe.com/indesign/desktop/automation-and-scripting/merge-data/merge-records.html
- Adobe InDesign, preflight de libros: https://helpx.adobe.com/indesign/desktop/print/preflight/preflight-book-files.html
- Adobe InDesign, preflight y empaquetado: https://helpx.adobe.com/uk/indesign/using/preflighting-files-handoff.html
- Adobe Acrobat, Output Preview: https://helpx.adobe.com/acrobat/using/previewing-output-acrobat-pro.html
- Adobe Acrobat, herramientas de producción: https://helpx.adobe.com/acrobat/using/print-production-tools-overview-acrobat.html
- Adobe Acrobat, PDF/X-4: https://helpx.adobe.com/acrobat/desktop/print-documents/set-up-and-print-pdfs/print-ready.html

Estas referencias fundamentan el proceso de salida y control; las decisiones de marca, composición y
flujo son propias de Perfect Catalog.
