# Resultado de la instalación controlada de PostgreSQL 18.6

> **Estado actualizado el 2026-08-17:** PostgreSQL 18.6 x64 está instalado con desviaciones, pero
> fue contenido mediante parada ordenada e inicio manual. No se autoriza crear roles, crear
> `perfect_catalog_dev`, ejecutar SQL ni aplicar el DDL. La siguiente compuerta es autorizar la
> desinstalación gráfica controlada descrita en `POSTGRESQL_REMEDIATION_PLAN.md`.

## 1. Control previo

Antes de abrir el asistente interactivo se reconfirmó:

- instalador exacto:
  `C:\Users\Diseño2\Downloads\PerfectCatalog\PostgreSQL\18.6\postgresql-18.6-1-windows-x64.exe`;
- SHA-256 exacto:
  `cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1`;
- firma Authenticode `Valid` de EnterpriseDB Corporation;
- PostgreSQL y el servicio `postgresql-x64-18` ausentes;
- puerto 5432 libre;
- Git limpio en `bf4d32c Verify PostgreSQL 18.6 installer artifact`.

El asistente fue abierto de forma interactiva. El usuario atendió personalmente UAC, la selección
del asistente y la contraseña. Codex no automatizó clics, no recibió la contraseña y no la guardó
en comandos, archivos, variables, documentación ni Git.

## 2. Versión y componentes observados

| Elemento | Resultado |
|---|---|
| PostgreSQL | `18.6-1`, instalado |
| `psql --version` | `psql (PostgreSQL) 18.6` |
| `pg_isready --version` | `pg_isready (PostgreSQL) 18.6` |
| PostgreSQL Server | Instalado y en ejecución |
| Command Line Tools | Instaladas |
| pgAdmin 4 | No detectado en rutas, comandos ni programas registrados |
| Stack Builder | `bin\stackbuilder.exe` presente y ejecutado accidentalmente; cerrado sin pulsar `Next` en la selección de complementos |
| Complementos de Stack Builder | No aparecen complementos adicionales en los programas registrados |

Stack Builder fue abierto por error después de la instalación. Las capturas mostraron varios
complementos seleccionados, pero todavía en la pantalla previa a `Next`; se indicó cancelar y cerrar.
No se observó ningún proceso Stack Builder activo durante la validación posterior.

## 3. Rutas

| Uso | Ruta aprobada | Resultado observado |
|---|---|---|
| Binarios | `C:\Program Files\PostgreSQL\18` | Existe |
| `psql.exe` | `C:\Program Files\PostgreSQL\18\bin\psql.exe` | Existe |
| `pg_isready.exe` | `C:\Program Files\PostgreSQL\18\bin\pg_isready.exe` | Existe |
| `initdb.exe` | `C:\Program Files\PostgreSQL\18\bin\initdb.exe` | Existe |
| Datos | `C:\PerfectCatalogData\postgresql\18\data` | **No existe** |
| Datos reales del servicio | No era la ruta aprobada | `C:\Program Files\PostgreSQL\18\data` |

La ubicación real de datos es una desviación. No se moverá el cluster ni se reinstalará el
servidor sin un plan de recuperación y una autorización específica.

## 4. Servicio y red

| Elemento | Resultado |
|---|---|
| Servicio | `postgresql-x64-18` |
| Nombre visible | `postgresql-x64-18` |
| Estado antes de contención | `Running` |
| Inicio antes de contención | `Auto` |
| Cuenta | `NT AUTHORITY\NetworkService` |
| Ejecutable asociado | `C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe` |
| Argumentos relevantes | `runservice -N "postgresql-x64-18" -D "C:\Program Files\PostgreSQL\18\data" -w` |
| Puerto | `5432` |
| `pg_isready -h localhost -p 5432` | `localhost:5432 - aceptando conexiones`, salida `0` |

La configuración efectiva observada en modo de solo lectura es:

```text
listen_addresses = '*'
port = 5432
```

Windows mostró listeners en `0.0.0.0:5432` y `[::]:5432`. Además,
`pg_isready -h 192.168.0.128 -p 5432` respondió `aceptando conexiones`. Esto incumple la escucha
inicial aprobada exclusivamente para localhost.

Las reglas `host` activas de `pg_hba.conf` observadas admiten solamente `127.0.0.1/32` y `::1/128`
con `scram-sha-256`, también para replicación. Esa restricción de autenticación no elimina la
desviación de escucha: antes de la contención el servidor seguía alcanzable en la interfaz
no-loopback. No se modificó `postgresql.conf`, `pg_hba.conf` ni el firewall en esta tarea.

### Contención posterior

Con autorización humana y UAC se detuvo ordenadamente solo `postgresql-x64-18` y su inicio cambió
de automático a manual. El estado vigente es `Stopped/Manual`, PID `0`, sin procesos
`postgres.exe`, sin listeners en 5432 y con `pg_isready` sin respuesta en localhost y LAN. No se
forzaron procesos ni se modificó configuración. La evidencia completa está en
[`POSTGRESQL_REMEDIATION_PLAN.md`](POSTGRESQL_REMEDIATION_PLAN.md).

## 5. Locale observado

El usuario reportó haber seleccionado **Español de Panamá / Spanish, Panama** en el asistente.
Sin embargo, `postgresql.conf` contiene:

```text
lc_messages = 'Spanish_Spain.1252'
lc_monetary = 'Spanish_Spain.1252'
lc_numeric = 'Spanish_Spain.1252'
lc_time = 'Spanish_Spain.1252'
```

Por tanto, el locale administrativo exacto del cluster no queda validado como Panamá y existe una
discrepancia que debe revisarse. Esto no cambia la decisión futura: `perfect_catalog_dev` no existe
y deberá crearse posteriormente desde `template0` con UTF8, proveedor ICU y locale `es-PA`, una
vez corregida y aprobada la configuración local.

## 6. Disponibilidad ICU

`initdb --help` reconoce las opciones requeridas:

```text
--locale-provider={builtin|libc|icu}
--icu-locale=LOCALE
```

No se ejecutó `initdb` ni se inicializó otro cluster.

## 7. Protecciones mantenidas

- No se guardaron, solicitaron ni documentaron contraseñas.
- No se ejecutó SQL ni el DDL.
- No se creó `perfect_catalog_dev`.
- No se crearon roles de aplicación.
- No se importó el Excel maestro.
- No se instalaron extensiones ni complementos de Stack Builder detectables.
- No se modificó PATH de usuario ni del equipo.
- No se modificaron firewall, `postgresql.conf` ni `pg_hba.conf`.
- No se habilitaron conexiones remotas mediante reglas HBA.
- El DDL y el Excel maestro permanecen sujetos a la comprobación final de hashes.

## 8. Desviaciones y siguiente compuerta

La instalación no cumple todavía el resultado aprobado debido a:

1. directorio de datos distinto del autorizado;
2. `listen_addresses = '*'` y escucha en interfaces no-loopback;
3. Stack Builder presente y ejecutado, aunque sin complementos detectados;
4. parámetros regionales `Spanish_Spain.1252` pese al locale Panamá reportado por el usuario.

La instalación desviada ya está contenida. La siguiente compuerta debe autorizar la desinstalación
gráfica controlada y preservar temporalmente el cluster incorrecto. El procedimiento posterior
deberá:

1. restringir la escucha a `localhost` y revalidar red/HBA;
2. decidir si se conserva el cluster actual o se reinstala controladamente para usar la ruta de
   datos aprobada;
3. revisar el locale administrativo real;
4. decidir el tratamiento del ejecutable Stack Builder;
5. solamente después preparar roles y crear `perfect_catalog_dev` con ICU `es-PA`.

Hasta completar esa compuerta, no se autoriza crear la base, roles, tablas ni ejecutar el DDL.

## 9. Validación del proyecto

- `py -3.14 -m unittest discover -s tests -v`: 36 pruebas, todas aprobadas.
- `git diff --check`: sin errores.
- SHA-256 del DDL antes y después:
  `8602d170e3345c9694bd498bd9f23162b72bd740e582fa3caa6a2bad3a1d660c`.
- SHA-256 del Excel maestro antes y después:
  `a8921bc428ce3d318de189237384fc2119383febca57fdc9a86d47844407b8`.
- El Excel continúa ignorado y el instalador permanece fuera del repositorio.
- Git no rastrea `.exe`, logs, Excel/CSV empresariales ni archivos temporales de esta tarea.

La contención exitosa permite versionar conjuntamente el resultado, el plan y la remediación sin
afirmar que la instalación desviada esté aprobada. La configuración y los archivos del servidor no
fueron alterados.
