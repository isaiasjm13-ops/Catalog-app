# Perfect Trading Catalog System

**Système local de catálogo de autopartes para Perfect Trading**

```
┌─ Perfect Trading (Empresa)
│  ├─ Perfect (Marca)
│  └─ Natsuki (Marca) ← Primera implementación
│     └─ 25,000+ referencias
```

## Inicio Rápido

### Requisitos (Actual)
- Windows 11 Pro (verificado ✓)
- Git 2.54.0+ (verificado ✓)
- Python 3.14.5+ (verificado ✓)
- Adobe InDesign 2026 (para exportación) (verificado ✓)

### Requisitos (Fase posterior)
- PostgreSQL 14+
- pgAdmin (opcional)

## Arquitectura Inicial

- **Base de datos oficial**: PostgreSQL. SQLite no se utilizará como base principal; solo podrá considerarse para pruebas aisladas si fuera necesario.
- **Backend oficial**: FastAPI.
- **Frontend inicial**: Jinja2 + HTML + CSS + JavaScript.
- **React**: No se utilizará inicialmente.

La interfaz seguirá siendo premium, responsive y moderna. Este stack reduce la complejidad inicial sin limitar el diseño, y la arquitectura podrá evolucionar hacia un frontend separado si una necesidad real lo justifica más adelante.

### Primeros Pasos

```bash
# 1. Clonar o entrar al repositorio
cd C:\PERFECT_CATALOG

# 2. Ver estado actual
git status

# 3. Revisar documentación
type PROJECT.md
type HANDOFF.md
```

## Odoo Profiler v0.1

Analiza exportaciones de Odoo en modo de solo lectura y genera reportes en `data/exports/profiles/`.

```powershell
py -3.14 -m tools.odoo_profiler "data\imports\NATSUKI_EMPAQUES_MAESTRO.xlsx"
```

Consulte [docs/ODOO_PROFILER.md](docs/ODOO_PROFILER.md) para opciones adicionales y ejecución de pruebas.

## Muestra Maestra Preliminar de Odoo

La exportación local `NATSUKI_EMPAQUES_MAESTRO.xlsx` proviene del modelo `product.template`
con marca NATSUKI y categoría de producto que contiene “empaque”. Contiene 893 productos en
13 columnas y su estructura fue validada con Odoo Profiler v0.1.

La especificación preliminar de [docs/DATA_SPEC.md](docs/DATA_SPEC.md) se basa en esta evidencia
real. El Excel fuente y los reportes generados permanecen locales e ignorados por Git.

PostgreSQL, FastAPI y Jinja2 + HTML + CSS + JavaScript continúan siendo la arquitectura oficial.
La arquitectura de datos v0.1 está aprobada documentalmente, pero no implementada. PostgreSQL
continúa sin instalar y todavía no existen DDL, tablas, migraciones ni importador. El siguiente
paso es convertir el diseño aprobado en un DDL revisable y una estrategia de migraciones, antes
de instalar el servicio.

## Arquitectura de Datos v0.1

- [docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md): diseño v0.1 aprobado documentalmente de
  24 tablas propuestas, trazabilidad, staging inmutable, planes exactos y versionado de catálogos.
- [docs/IMPORTER_DESIGN.md](docs/IMPORTER_DESIGN.md): flujo v0.1 aprobado documentalmente del
  importador, plan persistido, revisión/aprobación previa y mapeo de las 13 columnas reales.

Ambos diseños están aprobados únicamente como arquitectura. No autorizan instalar PostgreSQL ni
implementar el esquema o el importador.

## Documentación

- **[PROJECT.md](PROJECT.md)** - Visión general, reglas, arquitectura
- **[HANDOFF.md](HANDOFF.md)** - Estado actual, próximos pasos, bloqueadores
- **[AGENTS.md](AGENTS.md)** - Roles y responsabilidades de equipos
- **[docs/DATA_SPEC.md](docs/DATA_SPEC.md)** - Especificación preliminar de los datos de Odoo
- **[docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - Propuesta no implementada del modelo PostgreSQL
- **[docs/IMPORTER_DESIGN.md](docs/IMPORTER_DESIGN.md)** - Propuesta no implementada del importador de Odoo
- **[docs/ODOO_PROFILER.md](docs/ODOO_PROFILER.md)** - Uso y pruebas del perfilador de Odoo
- **[README.md](README.md)** - Este archivo

## Estructura de Carpetas (Planificada)

```
C:\PERFECT_CATALOG/
├── data/
│   ├── imports/          # Excel/CSV de Odoo
│   ├── images/           # Imágenes originales (no versionadas)
│   ├── exports/          # Salidas generadas
│   └── backups/          # Respaldos
├── src/                  # Código fuente (fase posterior)
├── logs/                 # Logs de ejecución
├── docs/                 # Documentación adicional
│
├── PROJECT.md            # Especificación del proyecto
├── HANDOFF.md           # Estado y próximos pasos
├── AGENTS.md            # Roles del equipo
├── README.md            # Este archivo
├── .env.example         # Variables de entorno (ejemplo)
├── .gitignore           # Exclusiones de Git
└── .git/                # Repositorio Git
```

## Workflow

1. **Sesión Actual**: Revisión de HANDOFF.md
2. **Trabajo**: Marca items completados con ✓
3. **Bloqueo**: Escala a Coordinador
4. **Fin de Sesión**: Actualiza HANDOFF.md y hace commit

## Comando Git Rápido

```bash
# Ver commits
git log --oneline

# Ver cambios
git status

# Hacer commit
git add .
git commit -m "Descripción clara del cambio"

# Ver rama
git branch -a
```

## Estado Actual

| Componente | Estado |
|-----------|--------|
| Documentación | ✓ Especificación real y arquitectura de datos v0.1 aprobada documentalmente |
| Base de Datos | PostgreSQL definido; diseño de 24 tablas aprobado, no implementado |
| Importador | Flujo, staging versionado y plan aprobado documentalmente; no implementado |
| Backend | FastAPI definido; implementación pendiente |
| Frontend | Jinja2 + HTML + CSS + JavaScript definidos; implementación pendiente |
| Exportación | ⏳ Pendiente BD |
| InDesign | ⏳ Pendiente exportación |

## Contactos

- Revisar HANDOFF.md para escalaciones
- Cualquier cambio en reglas: actualizar PROJECT.md

---

**Última actualización**: 2026-08-17  
**Responsable sesión**: Refinamiento y aprobación documental de arquitectura de datos v0.1
**Siguiente revisión**: DDL revisable y estrategia de migraciones antes de instalar PostgreSQL
