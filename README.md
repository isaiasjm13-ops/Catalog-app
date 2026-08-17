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

### Requisitos instalados y pendientes
- PostgreSQL 18.6 x64 desinstalado; cluster residual en cuarentena y reinstalación pendiente
- pgAdmin no instalado y aplazado

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
La arquitectura de datos v0.1 está aprobada y cuenta con un DDL v0.2 corregido, transaccional y
aprobado después de la segunda revisión manual, y una estrategia documental de migraciones. El SQL
no se ha ejecutado: PostgreSQL fue desinstalado y su cluster residual está en cuarentena, no existe
ninguna tabla del proyecto y el importador tampoco está implementado.

## Arquitectura de Datos v0.1

- [docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md): diseño v0.1 aprobado documentalmente de
  24 tablas propuestas, trazabilidad, staging inmutable, planes exactos y versionado de catálogos.
- [docs/IMPORTER_DESIGN.md](docs/IMPORTER_DESIGN.md): flujo v0.1 aprobado documentalmente del
  importador, plan persistido, revisión/aprobación previa y mapeo de las 13 columnas reales.
- [db/migrations/0001_initial_schema.sql](db/migrations/0001_initial_schema.sql): DDL v0.2 corregido
  de las 24 tablas bajo `perfect_catalog`; segunda revisión manual aprobada y no ejecutado.
- [docs/MIGRATION_STRATEGY.md](docs/MIGRATION_STRATEGY.md): política forward-only, revisión,
  backfills, expand/migrate/contract y futura adopción de Alembic.
- [docs/DDL_REVIEW.md](docs/DDL_REVIEW.md): matriz de tablas, conteos, límites y checklist previo.

El DDL tiene pruebas estáticas con la biblioteca estándar. Estas pruebas no autorizan instalar
PostgreSQL ni sustituyen una ejecución futura en una base vacía de prueba.

## Preparación de PostgreSQL local

El diagnóstico previo a la instalación fue realizado sin modificar el equipo. No se encontraron
binarios, servicios, procesos, rutas, claves de registro ni puertos PostgreSQL activos. Se preparó
[docs/POSTGRESQL_INSTALL_PLAN.md](docs/POSTGRESQL_INSTALL_PLAN.md) con la versión, fuente, rutas,
configuración, roles, recuperación y checklist propuestos.

La discrepancia entre la referencia oficial anterior 18.4 y `18.6-1` reportado por winget fue
revisada contra fuentes primarias. PostgreSQL.org identifica actualmente 18.6 como publicación
estable del 2026-08-13; winget queda solo como contraste y nunca como prueba oficial. La base futura
`perfect_catalog_dev` usará UTF8, proveedor ICU, locale `es-PA` y collation determinista. Las
búsquedas insensibles a mayúsculas/acentos se resolverán separadamente sin alterar la identidad
exacta de las referencias internas.

El instalador PostgreSQL 18.6 x64 se verificó y después se ejecutó interactivamente con
autorización humana expresa. La instalación presentó desviaciones, fue contenida y finalmente
desinstalada desde Programas y características de Windows tras validar alternativamente el
desinstalador sin firma. Ya no existen la aplicación, servicio, procesos, listeners ni binarios.

Consulte [docs/POSTGRESQL_INSTALLATION_RESULT.md](docs/POSTGRESQL_INSTALLATION_RESULT.md) y
[docs/POSTGRESQL_REMEDIATION_PLAN.md](docs/POSTGRESQL_REMEDIATION_PLAN.md).

No se creó ninguna base o rol de aplicación y no se ejecutó SQL. El cluster residual se movió
íntegro a `C:\PerfectCatalogData\quarantine\postgresql-18-incorrect-20260817\data`, con ACL
restringida. Los dos logs sensibles exactos fueron eliminados sin leerlos o copiarlos y Program
Files quedó sin restos PostgreSQL. La siguiente compuerta es la reinstalación interactiva con
directorio correcto y contraseña nueva; la cuarentena no debe eliminarse.

## Documentación

- **[PROJECT.md](PROJECT.md)** - Visión general, reglas, arquitectura
- **[HANDOFF.md](HANDOFF.md)** - Estado actual, próximos pasos, bloqueadores
- **[AGENTS.md](AGENTS.md)** - Roles y responsabilidades de equipos
- **[docs/DATA_SPEC.md](docs/DATA_SPEC.md)** - Especificación preliminar de los datos de Odoo
- **[docs/DATABASE_DESIGN.md](docs/DATABASE_DESIGN.md)** - Arquitectura aprobada y mapeo al DDL no ejecutado
- **[docs/IMPORTER_DESIGN.md](docs/IMPORTER_DESIGN.md)** - Diseño aprobado del importador, todavía sin código
- **[docs/MIGRATION_STRATEGY.md](docs/MIGRATION_STRATEGY.md)** - Estrategia documental de migraciones
- **[docs/DDL_REVIEW.md](docs/DDL_REVIEW.md)** - Revisión estática y correcciones del DDL v0.2
- **[docs/POSTGRESQL_INSTALL_PLAN.md](docs/POSTGRESQL_INSTALL_PLAN.md)** - Plan local, resultado real y correcciones pendientes
- **[docs/POSTGRESQL_INSTALLER_VERIFICATION.md](docs/POSTGRESQL_INSTALLER_VERIFICATION.md)** - Evidencia del instalador PostgreSQL 18.6 verificado y no ejecutado
- **[docs/POSTGRESQL_INSTALLATION_RESULT.md](docs/POSTGRESQL_INSTALLATION_RESULT.md)** - Instalación desviada, contención y desinstalación controlada
- **[docs/POSTGRESQL_REMEDIATION_PLAN.md](docs/POSTGRESQL_REMEDIATION_PLAN.md)** - Cluster en cuarentena, logs retirados y reinstalación pendiente
- **[db/migrations/0001_initial_schema.sql](db/migrations/0001_initial_schema.sql)** - DDL v0.2 no ejecutado
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
├── db/
│   └── migrations/       # Migraciones PostgreSQL revisables
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
| Documentación | ✓ Arquitectura, DDL, verificación e instalación documentadas |
| Base de Datos | PostgreSQL 18.6 desinstalado; cluster en cuarentena y sin base, roles, SQL ni tablas del proyecto |
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

**Responsable sesión**: Cuarentena del cluster residual y eliminación exacta de logs sensibles

**Siguiente revisión**: Reinstalar interactivamente PostgreSQL 18.6 con directorio correcto y contraseña nueva
