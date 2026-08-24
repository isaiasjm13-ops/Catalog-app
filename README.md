# Perfect Trading Catalog System

**Système local de catálogo de autopartes para Perfect Trading**

```
┌─ Perfect Trading (Empresa)
│  ├─ Perfect (Marca)
│  └─ Natsuki (Marca) ← Primera implementación
│     └─ 25,000+ referencias
```

## Inicio Rápido

### Requisitos
- Windows 11 Pro (verificado ✓)
- Git 2.54.0+ (verificado ✓)
- Python 3.14.5+ (verificado ✓)
- PostgreSQL 18.6 local (instalado y limitado a localhost)
- Adobe InDesign 2026 (para exportación) (verificado ✓)

## Arquitectura Inicial

- **Base de datos oficial**: PostgreSQL. SQLite no se utilizará como base principal; solo podrá considerarse para pruebas aisladas si fuera necesario.
- **Backend oficial**: FastAPI.
- **Frontend inicial**: Jinja2 + HTML + CSS + JavaScript.
- **React**: No se utilizará inicialmente.

La interfaz seguirá siendo premium, responsive y moderna. Este stack reduce la complejidad inicial sin limitar el diseño, y la arquitectura podrá evolucionar hacia un frontend separado si una necesidad real lo justifica más adelante.

### Primeros Pasos

```powershell
# 1. Clonar o entrar al repositorio
cd C:\PERFECT_CATALOG

# 2. Crear el entorno si todavía no existe
py -3.14 -m venv .venv

# 3. Instalar aplicación y dependencias de prueba
.\.venv\Scripts\python.exe -m pip install -e ".[test]"

# 4. Copiar una exportación autorizada a data\imports (no se versiona)

# 5. Iniciar catálogo y API de solo lectura
.\INICIAR-SERVER.cmd
```

Abrir:

- Catálogo: `http://127.0.0.1:8080/`
- Documentación OpenAPI: `http://127.0.0.1:8080/docs`
- Estado: `http://127.0.0.1:8080/api/v1/health`

El servidor detecta el XLSX más reciente de `data/imports`. Para fijar una fuente concreta:

```powershell
.\.venv\Scripts\perfect-catalog-api.exe --source "data\imports\NATSUKI_EMPAQUES_MAESTRO.xlsx"
```

La API piloto expone:

- `GET /api/v1/products?q=&category=&limit=&offset=`
- `GET /api/v1/products/{fila_origen}`
- `GET /api/v1/categories`

Los IDs `source-row:*` son provisionales. No deben tratarse como identidad empresarial; los UUID
estables llegarán desde los productos/releases publicados en PostgreSQL.

### Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las dos pruebas de integración PostgreSQL son opt-in porque solicitan credenciales de forma
interactiva. El procedimiento controlado está en `scripts/run_productive_block_validation.ps1`.

### Estado y auditoría

La matriz vigente de requisitos y el plan por dependencias están en
[`docs/STATUS_AUDIT_V2_2.md`](docs/STATUS_AUDIT_V2_2.md). El manual PDF v2.2 no está presente en el
repositorio ni en el adjunto recibido; la auditoría es provisional respecto de su texto literal.

```powershell
# Revisar estado actual
git status

# Revisar documentación de continuidad
type PROJECT.md
type HANDOFF.md
```

## Documentación

- **[PROJECT.md](PROJECT.md)** - Visión general, reglas, arquitectura
- **[HANDOFF.md](HANDOFF.md)** - Estado actual, próximos pasos, bloqueadores
- **[AGENTS.md](AGENTS.md)** - Roles y responsabilidades de equipos
- **[README.md](README.md)** - Este archivo

## Estructura principal

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
| Documentación | ✓ Arquitectura inicial definida |
| Base de Datos | PostgreSQL instalado; 24 tablas/migraciones validadas previamente; integración actual opt-in |
| Backend | FastAPI de consulta v1 implementada sobre fuente provisional XLSX/staging |
| Frontend | Catálogo responsive y ficha imprimible piloto |
| Exportación | ⏳ Pendiente BD |
| InDesign | ⏳ Pendiente exportación |

## Contactos

- Revisar HANDOFF.md para escalaciones
- Cualquier cambio en reglas: actualizar PROJECT.md

---

**Última actualización**: 2026-08-24
**Siguiente revisión**: contrato flexible de importación y lectura desde releases publicados
