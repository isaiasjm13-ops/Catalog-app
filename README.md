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

La suite completa, incluidas las cuatro pruebas PostgreSQL y el dry-run real, se ejecuta con el
procedimiento controlado `scripts/run_productive_block_validation.ps1`. Solicita las credenciales
de forma interactiva y nunca las guarda. La ejecución del 2026-08-24 terminó con 95/95 pruebas y
`integration=0;import=0`.

El dry-run limita el piloto a 5,000 filas de forma predeterminada. `--max-rows` permite cambiar el
límite conscientemente, pero no debe ampliarse al catálogo completo antes de aprobar el piloto.

### Aprobación y aplicación controlada

El flujo transaccional está implementado y las migraciones `0003` y `0004` fueron aplicadas y
validadas en `perfect_catalog_dev`. La prueba de apply usa datos sintéticos y revierte la transacción.
Ningún plan empresarial fue aprobado ni aplicado.

```powershell
# Inspección de solo lectura
.\.venv\Scripts\perfect-catalog.exe inspect-plan <PLAN_UUID> --prompt-password

# Registra una aprobación humana del fingerprint exacto; todavía no escribe productos
.\.venv\Scripts\perfect-catalog.exe approve-plan <PLAN_UUID> `
  --fingerprint <SHA256_DE_64_CARACTERES> `
  --actor <USUARIO> --reason "Piloto revisado" --prompt-password

# Solo después de la autorización operacional expresa
.\.venv\Scripts\perfect-catalog.exe apply-plan <PLAN_UUID> `
  --fingerprint <EL_MISMO_SHA256> `
  --actor <USUARIO> --reason "Aplicación autorizada" --prompt-password
```

El detalle de estados, controles, alcance y recuperación está en
[`docs/APPLY_WORKFLOW.md`](docs/APPLY_WORKFLOW.md).

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
| Base de Datos | PostgreSQL instalado; migraciones `0001`–`0004` aplicadas y validadas localmente |
| Backend | FastAPI de consulta v1 implementada sobre fuente provisional XLSX/staging |
| Apply | Workflow transaccional validado con el rol real y rollback sintético; plan empresarial no autorizado |
| Frontend | Catálogo responsive y ficha imprimible piloto |
| Exportación | ⏳ Pendiente BD |
| InDesign | ⏳ Pendiente exportación |

## Contactos

- Revisar HANDOFF.md para escalaciones
- Cualquier cambio en reglas: actualizar PROJECT.md

---

**Última actualización**: 2026-08-24
**Siguiente revisión**: read model estable desde `catalog_release`
