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

# 4. Actualizar la base después de recibir una versión nueva
.\ACTUALIZAR-SISTEMA.cmd

# 5. Iniciar la consola principal de trabajo
.\INICIAR-REVISOR.cmd
```

Abrir:

- Consola de trabajo: `http://127.0.0.1:8081/operator`
- Catálogo publicado (con `INICIAR-CATALOGO-PUBLICADO.cmd`): `http://127.0.0.1:8080/`

### Qué significa “actualizar la base”

El código y PostgreSQL evolucionan juntos. Los archivos numerados de `db/migrations` conservan el
historial técnico de esos cambios y no son accesos de uso diario. No debes escogerlos manualmente:
`ACTUALIZAR-SISTEMA.cmd` consulta la base, detecta lo que falta y aplica solamente esos cambios.
Desde la versión 1.37 también habilita Company activa de extremo a extremo: al entrar se elige la
empresa de trabajo y sus ingresos, imágenes, planes, marcas, catálogos e identidad corporativa se
muestran y procesan únicamente dentro de ese contexto.
Úsalo después de recibir una actualización que incluya cambios de base de datos o cuando la consola
lo indique. Para el trabajo normal abre únicamente `INICIAR-REVISOR.cmd`.

### Preparación multiempresa - Fase 0

Antes de cualquier migración multiempresa ejecuta una sola vez `PREPARAR-MULTIEMPRESA.cmd`.
Solicita la contraseña de `postgres` de forma oculta, crea un backup lógico completo bajo
`backups/phase0-multicompany/`, comprueba que `pg_restore` pueda leerlo y genera allí un informe
de sólo lectura con esquema, marcas, productos, releases, referencias, identidades y permisos.
No modifica PostgreSQL ni aplica migraciones. El informe se usa para completar y aprobar
[`docs/MAPPING-COMPANY-BRAND-INICIAL.md`](docs/MAPPING-COMPANY-BRAND-INICIAL.md).

Al hacer doble clic en `INICIAR-SERVER.cmd`, la web queda visible en
`http://127.0.0.1:8080/`. Ese iniciador conserva deliberadamente el piloto XLSX y detecta el archivo más reciente de
`data/imports`. Para fijar una fuente concreta:

```powershell
.\.venv\Scripts\perfect-catalog-api.exe --source "data\imports\NATSUKI_EMPAQUES_MAESTRO.xlsx"
```

Para consultar el último release publicado e inmutable desde PostgreSQL, usa
`INICIAR-CATALOGO-PUBLICADO.cmd`. Solicita la contraseña de forma oculta y conserva el servidor en
modo de sólo lectura; no utiliza el XLSX piloto ni muestra credenciales en argumentos.

La misma aplicación expone:

- `GET /api/v1/products?q=&category=&limit=&offset=`
- `GET /api/v1/products/{product_id}`
- `GET /api/v1/categories`

### Consola local de revisión

Después de actualizar el código, ejecuta una sola vez `ACTUALIZAR-SISTEMA.cmd`. El actualizador
detecta automáticamente qué cambios de base de datos faltan, los aplica en orden y conserva
permisos mínimos; no debes elegir ni ejecutar migraciones individuales.

La revisión humana usa un servidor separado del catálogo público. Haz doble clic en
`INICIAR-REVISOR.cmd` e introduce únicamente la contraseña de PostgreSQL para
`perfect_catalog_app`. El iniciador toma el usuario de Windows como actor de auditoría, genera un
código web temporal fuerte y abre automáticamente el login en el navegador predeterminado.

Copia en la página el código visible en la consola. La contraseña de PostgreSQL nunca se escribe en
el navegador ni se guarda en el proyecto. La sesión dura una hora y desaparece al detener el
servidor. Para una identidad o código elegidos manualmente siguen disponibles las opciones
`--prompt-operator` y `--prompt-access-code` de la CLI.

El modo operador lista planes aplicados, pagina 50 identidades por vista, busca por referencia,
nombre o fila, filtra estados y permite aprobar/rechazar una sola ficha con motivo obligatorio. Usa
el mismo fingerprint y `review_sha256` de la CLI. Está aislado en localhost, no monta el catálogo
público ni OpenAPI, y aplica sesión firmada, CSRF, validación de origen, escape HTML y cabeceras CSP.

En **Marcas** se administran dos niveles separados de identidad visual: la identidad madre de
Perfect Trading para la portada común y el logo/colores propios de cada marca de producto. Cada
cambio crea una revisión auditada; no sobrescribe el historial. Los logos admiten PNG, JPG y SVG
seguros (máximo 5 MiB). Usa PNG o JPG cuando el mismo archivo deba aparecer también en PDF y
PowerPoint; SVG se conserva para HTML e InDesign. La identidad queda congelada al construir una
versión nueva, por lo que un release anterior no cambia retroactivamente.
Los cuatro colores congelados gobiernan también la vista previa y todos los formatos exportados:
el principal define jerarquía, el secundario aporta acentos, y texto/fondo controlan legibilidad.
El tema editorial elegido solo actúa como respaldo si no existe un perfil de marca.
En el catálogo HTML, tocar una fotografía abre una ficha completa responsive con referencia,
categoría, aplicaciones, motor y OEM; la imagen se muestra entera y el visor continúa offline.
La marca seleccionada controla la dirección visual. La Company aporta su logo de portada y una
firma cromática discreta en los pies de HTML, PDF, PowerPoint e InDesign, sin reemplazar los colores
de Natsuki, Exact Cars u otra marca de producto.
El HTML permite filtrar offline por categoría, marca y vehículo, alternar Tarjetas/Lista y recuperar
la búsqueda, filtros, vista y posición de lectura al volver a abrir la misma edición.
Su buscador offline acepta varias palabras en cualquier orden, ignora acentos y encuentra códigos
con o sin espacios/guiones. También indexa aplicaciones, motores, OEM y referencias adicionales
aunque esos campos se hayan ocultado visualmente en la edición.
El compositor de **Catálogos** conserva automáticamente un borrador local independiente por release
y muestra un resumen vivo. No almacena credenciales ni confirmaciones, y puede restablecerse desde
la misma pantalla.
La selección de productos también puede hacerse visualmente: el buscador paginado muestra referencia,
categoría, aplicaciones, motor y miniatura, y transfiere las casillas al contrato exacto de referencias.
En **Marcas**, los formularios ofrecen una vista previa local de portada, ficha y marca de agua antes
de guardar, además de comprobar contraste 4.5:1 entre texto/fondo y color principal/fondo.
El selector visual admite ordenar las referencias elegidas. Para HTML también pueden ocultarse
categoría, marca, OEM, aplicaciones o motor; el mismo ajuste aparece en la vista previa y el borrador.
El script de InDesign incorpora compatibilidad JSON propia para versiones antiguas de ExtendScript;
no es necesario actualizar InDesign únicamente por ausencia de `JSON.parse`.
La composición InDesign adapta fichas T4 extensas a T2/T1 para conservar texto mínimo de 12 pt e
interlineado 1.8; las fichas sin imagen recuperan el espacio fotográfico en vez de quedar vacías.

La misma pantalla permite asociar un logo independiente a cada marca vehicular aprobada. Este
activo aparece únicamente junto al nombre de la marca del vehículo cuando el catálogo se agrupa
por ese campo; no sustituye el logo de Perfect Trading ni el de la marca del producto. Después de
recibir esta función, ejecuta una vez `ACTUALIZAR-SISTEMA.cmd` para aplicar la migración `0016`.

La misma consola incorpora un centro de ingreso en `/operator/intake`. Si el actualizador lo solicita,
ejecuta `ACTUALIZAR-SISTEMA.cmd`. Recibe XLSX/CSV/TSV de Odoo, PDF y paquetes ZIP de imágenes o
InDesign, calcula SHA-256 y los conserva en cuarentena sin importar ni publicar automáticamente.
Véase [`docs/INTAKE_WORKFLOW.md`](docs/INTAKE_WORKFLOW.md).

Un dry-run se inspecciona desde **Ingresos** mediante **Inspeccionar y autorizar plan**. La consola
web exige dos decisiones separadas y auditadas: primero aprobar el fingerprint exacto (sin escribir
productos) y luego aplicar el plan aprobado. Los productos aplicados quedan pendientes de revisión
individual; sus OEM, FMSI y referencias adicionales detectadas se muestran y resuelven junto con la
misma identidad. Nunca se publican automáticamente. Véase [`docs/OPERATOR_WEB.md`](docs/OPERATOR_WEB.md).

Sin `--source` ni `--source-dir`, la API v1.2 lee por defecto el último release publicado de la
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

La suite completa, incluidas las seis pruebas PostgreSQL y el dry-run real, se ejecuta con el
procedimiento controlado `scripts/run_productive_block_validation.ps1`, o haciendo doble clic en
`VALIDAR-BLOQUE.cmd`. Solicita las credenciales de forma interactiva y nunca las guarda. La
ejecución del 2026-08-24 terminó con 143/143 pruebas y `integration=0;import=0`.

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
| Base de Datos | PostgreSQL instalado; migraciones `0001`–`0007` aplicadas y validadas localmente |
| Backend | FastAPI v1.2: catálogo de identidad sin inventario/precios; release publicado con UUID por defecto y modo piloto XLSX explícito |
| Apply | Workflow transaccional validado con el rol real y rollback sintético; plan empresarial no autorizado |
| Revisión | Consola web local protegida, paginada y validada; plan empresarial aún no aplicado |
| Ingreso | Cuarentena web trazable para Odoo, imágenes, PDF e InDesign; procesamiento posterior explícito |
| Frontend | Catálogo responsive y ficha imprimible piloto |
| Exportación | ⏳ Pendiente BD |
| InDesign | ⏳ Pendiente exportación |

## Contactos

- Revisar HANDOFF.md para escalaciones
- Cualquier cambio en reglas: actualizar PROJECT.md

---

**Última actualización**: 2026-08-24
**Siguiente revisión**: revisión y activación humana de productos/referencias aplicados
