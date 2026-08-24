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

# 5. Iniciar el piloto local sobre el XLSX más reciente
.\INICIAR-SERVER.cmd
```

Abrir:

- Catálogo: `http://127.0.0.1:8080/`
- Documentación OpenAPI: `http://127.0.0.1:8080/docs`
- Estado: `http://127.0.0.1:8080/api/v1/health`

Al hacer doble clic en `INICIAR-SERVER.cmd`, la web queda visible en
`http://127.0.0.1:8080/`. Ese iniciador conserva deliberadamente el piloto XLSX y detecta el archivo más reciente de
`data/imports`. Para fijar una fuente concreta:

```powershell
.\.venv\Scripts\perfect-catalog-api.exe --source "data\imports\NATSUKI_EMPAQUES_MAESTRO.xlsx"
```

La misma aplicación expone:

- `GET /api/v1/products?q=&category=&limit=&offset=`
- `GET /api/v1/products/{product_id}`
- `GET /api/v1/categories`

### Consola local de revisión

La revisión humana usa un servidor separado del catálogo público. Haz doble clic en
`INICIAR-REVISOR.cmd`; la consola solicitará, en este orden:

1. contraseña de PostgreSQL para `perfect_catalog_app`;
2. nombre del operador que quedará en auditoría;
3. un código temporal de al menos 12 caracteres y su confirmación.

Después abre `http://127.0.0.1:8081/operator` e introduce únicamente el código temporal. La
contraseña de PostgreSQL nunca se escribe en el navegador. La sesión dura una hora y desaparece al
detener el servidor.

El modo operador lista planes aplicados, pagina 50 identidades por vista, busca por referencia,
nombre o fila, filtra estados y permite aprobar/rechazar una sola ficha con motivo obligatorio. Usa
el mismo fingerprint y `review_sha256` de la CLI. Está aislado en localhost, no monta el catálogo
público ni OpenAPI, y aplica sesión firmada, CSRF, validación de origen, escape HTML y cabeceras CSP.

Actualmente la pantalla mostrará “No hay planes aplicados para revisar”: es correcto, porque ningún
plan empresarial ha sido aplicado. Véase [`docs/OPERATOR_WEB.md`](docs/OPERATOR_WEB.md).

Sin `--source` ni `--source-dir`, la API v1.1 lee por defecto el último release publicado de la
marca solicitada y expone UUID estables. El release completo y cada snapshot se validan contra sus
checksums antes de responder:

```powershell
.\.venv\Scripts\perfect-catalog-api.exe --brand NATSUKI --prompt-password
```

Actualmente no existe un release empresarial publicado, por lo que ese comando debe fallar de
forma explícita hasta completar una publicación controlada. Los IDs `source-row:*` solo existen en
el modo piloto XLSX y nunca deben tratarse como identidad empresarial. El contrato del read model
se documenta en [`docs/RELEASE_READ_MODEL.md`](docs/RELEASE_READ_MODEL.md).

### Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

La suite completa, incluidas las cinco pruebas PostgreSQL y el dry-run real, se ejecuta con el
procedimiento controlado `scripts/run_productive_block_validation.ps1`, o haciendo doble clic en
`VALIDAR-BLOQUE.cmd`. Solicita las credenciales de forma interactiva y nunca las guarda. La
ejecución del 2026-08-24 terminó con 128/128 pruebas y `integration=0;import=0`.

El dry-run limita el piloto a 5,000 filas de forma predeterminada. `--max-rows` permite cambiar el
límite conscientemente, pero no debe ampliarse al catálogo completo antes de aprobar el piloto.

### Aprobación y aplicación controlada

El flujo transaccional está implementado y las migraciones `0003`–`0006` fueron aplicadas y
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

### Revisión humana de productos aplicados

Cada alta aplicada queda en `pending_review`; no se activa por lote ni se publica por omisión. La
cola devuelve un `review_sha256` distinto por identidad, ligado al plan, fila fuente, nombre y
referencia visibles. La decisión actualiza atómicamente producto y referencia, exige actor/motivo,
registra auditoría e impide cambiar una decisión previa:

```powershell
.\.venv\Scripts\perfect-catalog.exe inspect-reviews <PLAN_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> --prompt-password

.\.venv\Scripts\perfect-catalog.exe review-product <PLAN_UUID> <PRODUCT_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> `
  --review-sha256 <HASH_MOSTRADO_PARA_ESE_PRODUCTO> `
  --decision approve `
  --actor <USUARIO> --reason "Identidad y referencia verificadas" --prompt-password
```

`--decision reject` deja producto y referencia inactivos/rechazados sin borrarlos. La CLI conserva
un límite explícito de 5,000 identidades para su salida completa; la consola web usa consultas
paginadas y no recorta silenciosamente. Ninguno de estos comandos está autorizado todavía sobre el
plan empresarial real. Véase
[`docs/PRODUCT_REVIEW_WORKFLOW.md`](docs/PRODUCT_REVIEW_WORKFLOW.md).

### Construcción y publicación controlada

Aplicar un plan no publica el catálogo. Un borrador solo puede construirse desde un plan aplicado,
sin identidades pendientes en la marca, y con productos `active` que tengan exactamente una
referencia interna primaria `approved`. La construcción
devuelve el checksum que debe inspeccionarse y aprobarse de forma separada:

```powershell
.\.venv\Scripts\perfect-catalog.exe build-release <PLAN_UUID> `
  --fingerprint <FINGERPRINT_APLICADO> --version <VERSION> `
  --actor <USUARIO> --reason "Construcción revisable" --prompt-password

.\.venv\Scripts\perfect-catalog.exe inspect-release <RELEASE_UUID> --prompt-password

.\.venv\Scripts\perfect-catalog.exe publish-release <RELEASE_UUID> `
  --snapshot-sha256 <CHECKSUM_EXACTO> `
  --actor <USUARIO> --reason "Publicación autorizada" --prompt-password
```

`archive-release` conserva el contenido y registra la transición final. La migración `0005` impide
modificar o borrar releases, items y auditoría fuera del workflow. No existe todavía un release
empresarial y estos comandos no están autorizados sobre el plan real actual. Véase
[`docs/RELEASE_PUBLICATION_WORKFLOW.md`](docs/RELEASE_PUBLICATION_WORKFLOW.md).

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
| Base de Datos | PostgreSQL instalado; migraciones `0001`–`0006` aplicadas y validadas localmente |
| Backend | FastAPI v1.1: release publicado con UUID por defecto y modo piloto XLSX explícito |
| Apply | Workflow transaccional validado con el rol real y rollback sintético; plan empresarial no autorizado |
| Revisión | Consola web local protegida, paginada y validada; plan empresarial aún no aplicado |
| Frontend | Catálogo responsive y ficha imprimible piloto |
| Exportación | ⏳ Pendiente BD |
| InDesign | ⏳ Pendiente exportación |

## Contactos

- Revisar HANDOFF.md para escalaciones
- Cualquier cambio en reglas: actualizar PROJECT.md

---

**Última actualización**: 2026-08-24
**Siguiente revisión**: revisión y activación humana de productos/referencias aplicados
