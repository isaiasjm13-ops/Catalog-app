# AGENTS.md - Agentes de Trabajo y Especialidades

## Propósito

Documento que define los roles, responsabilidades y especialidades de los agentes (humanos o IA) que trabajan en el proyecto Perfect Trading Catalog System.

## Agentes Principales

### Agent 1: Coordinador de Proyecto
- **Responsabilidad**: Visión general, arquitectura, decisiones estratégicas
- **Especialidad**: Diseño de sistemas, integraciones
- **Acciones Típicas**:
  - Definir estructura de base de datos
  - Planificar fases
  - Validar reglas de negocio
  - Resolver decisiones bloqueantes

### Agent 2: Ingeniero de Backend
- **Responsabilidad**: Importadores de datos, APIs, lógica de negocio
- **Especialidad**: Python, bases de datos, procesamiento de datos
- **Acciones Típicas**:
  - Crear importador de Excel/CSV
  - Desarrollar lógica de filtrado y agrupación
  - Crear APIs REST
  - Manejo de transacciones

### Agent 3: Ingeniero de Frontend
- **Responsabilidad**: Interfaz web, UX, navegación
- **Especialidad**: JavaScript, React/Vue, CSS
- **Acciones Típicas**:
  - Crear interfaz de búsqueda
  - Implementar filtros dinámicos
  - Navegación multi-nivel
  - Responsive design

### Agent 4: Especialista en Exportación
- **Responsabilidad**: Generación de PDFs e InDesign
- **Especialidad**: Adobe API, templating, generación de documentos
- **Acciones Típicas**:
  - Scripts de InDesign
  - Generación de PDFs
  - Control de plantillas T4, T2, T1, TABLE, SEPARATOR
  - Validación de imágenes y fuentes

### Agent 5: Analista de Datos / Odoo
- **Responsabilidad**: Estructura de datos, mapeo Odoo → Sistema
- **Especialidad**: Análisis de estructuras de datos, Odoo
- **Acciones Típicas**:
  - Analizar Excel de Odoo
  - Definir mapeo de campos
  - Documentar reglas de transformación
  - Validar calidad de datos

## Reglas de Comunicación Entre Agentes

1. **Cambios en Estructura**: Cualquier cambio en PROJECT.md requiere aprobación del Coordinador
2. **Bloqueos Críticos**: Se escalan inmediatamente al Coordinador
3. **Dependencias**: Se documentan en HANDOFF.md
4. **Decisiones**: Se registran en git commits con descripción clara

## Checklist de Entrada a Sesión

- [ ] Revisar HANDOFF.md para pendientes
- [ ] Verificar estado del último commit
- [ ] Revisar PROJECT.md para cambios
- [ ] Identificar bloqueadores

## Checklist de Salida de Sesión

- [ ] Actualizar HANDOFF.md con progreso y pendientes
- [ ] Hacer commit de cambios documentados
- [ ] Dejar código compilable (sin romper estado)
- [ ] Documentar cualquier decisión crítica

