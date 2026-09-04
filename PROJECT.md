# Nexo ISA — Sistema de Catálogo Multiempresa

## Visión General

Sistema local de catálogo de autopartes que posteriormente puede publicarse en web. Diseñado para gestionar más de 25,000 referencias inicialmente desde la marca Natsuki, con arquitectura preparada para múltiples marcas.

## Estructura Organizativa

- **Empresas confirmadas**: Perfect Trading y PDM (independientes)
- **Marcas de Perfect Trading confirmadas**: Natsuki, Masaki y Exact Cars
- **Marca corporativa de Perfect Trading**: Perfect
- **Marcas de PDM**: se administran dentro del contexto PDM y no heredan identidad de Perfect
- **Arquitectura**: multiempresa y multimarca; una marca pertenece a una sola empresa

## Fuente de Datos Maestra

- **Sistema Principal**: Odoo
- **Formato Inicial**: Excel/CSV
- **Importación**: Inicialmente manual, importador definitivo TBD tras análisis real

## Reglas No Negociables

### 1. Integridad de Datos
- Perfect Trading es la empresa.
- Perfect es una marca distinta dentro de Perfect Trading.
- Natsuki, Masaki y Exact Cars son marcas de Perfect Trading, no empresas.
- PDM es una empresa independiente; sus catálogos no muestran identidad de Perfect ni Natsuki.
- Las empresas pueden crearse y desactivarse desde la consola sin borrar su historial.
- Odoo será la fuente maestra de productos.
- No se eliminarán productos automáticamente.
- Las fotografías originales nunca se modificarán.
- Una misma pieza puede aparecer en varios catálogos o secciones sin duplicarse en la base.

### 2. Enfoque de Desarrollo
- El sistema trabajará localmente primero.
- No se definirá el importador definitivo de Odoo hasta analizar un Excel real.
- Toda ruta debe ser portable y evitar rutas absolutas innecesarias.

### 3. Escalabilidad de Marcas
- El sistema debe quedar preparado para múltiples marcas.
- Cada marca operará de forma independiente pero dentro de la misma infraestructura.

## Funcionalidades Requeridas

### Búsqueda y Filtrado
- Búsqueda por referencia Natsuki
- OEM (Original Equipment Manufacturer)
- Cross references
- FMSI (Fédération Mécanique Standardisée Internationale)
- Marca de vehículo
- Modelo
- Año
- Motor
- Categoría
- Línea

### Generación Dinámica de Catálogos

El sistema puede generar catálogos organizados por:

- Categoría
- Línea
- Marca de vehículo
- Modelo
- Motor
- Combinaciones de filtros
- Selección manual

**Conceptos Separados:**
- Filtrar: reducir el conjunto de datos
- Agrupar: organizar jerárquicamente (ej: marca > modelo > referencia)
- Ordenar: secuenciar dentro de un grupo

**Ejemplos de Organización:**

```
Natsuki + Empaques
└─ Marca de vehículo
   └─ Modelo
      └─ Referencia

Natsuki + Toyota
└─ Modelo
   └─ Categoría
      └─ Referencia
```

### Formatos de Salida

1. **Catálogo Web Local**
   - Interfaz de búsqueda interactiva
   - Navegación multi-filtro

2. **Ficha PDF Individual**
   - Información completa de la pieza
   - Especificaciones técnicas

3. **PDF Digital**
   - Compilado de fichas o secciones

4. **Catálogo Impreso (Adobe InDesign)**
   - Plantillas variables: T4, T2, T1, TABLE, SEPARATOR
   - Control de imágenes faltantes
   - Control de texto desbordado
   - Gestión de fuentes
   - Gestión de enlaces
   - Snapshots locales (no depende directamente de PostgreSQL)
   - Formato INDD editable antes de exportar PDF

## Escala

- **Volumen**: Más de 25,000 referencias
- **Ambiente Inicial**: Completamente local
- **Actualización de Datos**: Ciclos controlados desde Odoo

## Stack Tecnológico Inicial (Oficial)

- **Backend**: Python con FastAPI
- **Base de Datos**: PostgreSQL
  - PostgreSQL es la base de datos principal y oficial del proyecto.
  - SQLite no se utilizará como base principal; solo podría emplearse en pruebas aisladas si alguna vez fuera necesario.
- **Frontend Web Inicial**: Jinja2 + HTML + CSS + JavaScript
  - React no se utilizará inicialmente.
  - La interfaz deberá ser visualmente premium, responsive y moderna.
  - La elección del frontend inicial reduce la complejidad técnica sin limitar la calidad del diseño.
- **Exportación**: Adobe InDesign API/Scripts
- **Control de Versiones**: Git

La arquitectura permanecerá preparada para evolucionar hacia un frontend separado si las necesidades reales del proyecto lo justifican más adelante.

## Fases de Desarrollo

### Fase 1: Documentación y Estructura
- ✓ Diagnóstico del entorno
- ✓ Documentación del proyecto
- Análisis de Excel real desde Odoo
- Definición de estructura de base de datos

### Fase 2: Prototipo Local
- Carga de datos (Python)
- Base de datos PostgreSQL
- API básica con FastAPI

### Fase 3: Interfaz Web
- Renderizado inicial con Jinja2, HTML, CSS y JavaScript
- Búsqueda y filtrado
- Navegación

### Fase 4: Exportación
- PDF de fichas
- Generación de catálogos InDesign

### Fase 5: Web Pública
- Publicación
- Sincronización con Odoo

## Convenciones

- Todos los archivos de configuración van en la raíz
- Datos importados van en `data/imports/`
- Imágenes en `data/images/` (no versionadas)
- Exportaciones en `data/exports/`
- Logs en `logs/`
- Backups en `backups/`
- Rutas relativas siempre que sea posible

