# Plan de preparación para PostgreSQL local

> **Estado al 2026-08-17:** diagnóstico completado; instalador PostgreSQL 18.6 x64 descargado
> fuera del repositorio y verificado. PostgreSQL no está instalado, el archivo no fue ejecutado y
> la siguiente compuerta requiere autorización humana expresa.

Este documento define la instalación local futura de PostgreSQL para Perfect Catalog. La descarga
y verificación del artefacto exacto quedaron documentadas, pero no autorizan su ejecución,
instalación, creación de servicios, directorios operativos, roles, bases de datos ni ejecución del
DDL. Las decisiones marcadas como aprobadas fijan la propuesta futura; la autorización humana para
ejecutar el instalador continúa pendiente.

## 1. Diagnóstico de la estación de trabajo

### Windows y hardware

| Elemento | Resultado de solo lectura |
|---|---|
| Equipo | `PERFECT-DISEN02` |
| Sistema | Microsoft Windows 11 Pro, versión `10.0.26200`, build `26200` |
| Arquitectura | 64 bits |
| CPU | Intel Core Ultra 7 265, 20 procesadores lógicos |
| RAM | 31.43 GiB totales; 14.98 GiB disponibles durante el diagnóstico |
| Unidad C: | 920.43 GiB totales; 239.72 GiB libres durante el diagnóstico |
| Cultura de Windows | `es-PA` — Español (Panamá) |
| Zona horaria de Windows | `SA Pacific Standard Time`, UTC-05:00 |

Los valores disponibles son una fotografía del momento y deben comprobarse de nuevo antes de
instalar. El equipo tiene recursos suficientes para una instancia local de desarrollo conservadora.

### Permisos

- Usuario interactivo observado: `AzureAD\Diseño2`.
- La sesión no estaba elevada como administrador.
- Una instalación futura del servidor y el registro del servicio requerirán elevación UAC.
- PowerShell: `CurrentUser=RemoteSigned`, `LocalMachine=Restricted`; las demás políticas estaban
  sin definir. No se modificará ninguna política para instalar PostgreSQL.

### Ausencia de PostgreSQL y pgAdmin

Las siguientes comprobaciones no encontraron ningún rastro:

- comandos `psql`, `pg_config`, `postgres`, `pg_ctl`, `pg_dump`, `pg_restore` y `pgadmin4`;
- servicios o procesos con nombres PostgreSQL, PgSQL o pgAdmin;
- instalaciones registradas de PostgreSQL, pgAdmin o EnterpriseDB;
- claves `HKLM\SOFTWARE\PostgreSQL`, su equivalente de 32 bits y la clave de usuario;
- carpetas habituales bajo `Program Files`, `ProgramData`, `AppData\Roaming` o
  `AppData\Local`;
- entradas PostgreSQL/PgSQL/pgAdmin en el `PATH` de usuario o del equipo;
- listeners TCP en los puertos 5432 y 5433.

No hay evidencia local de una instalación completa o parcial. Esto no sustituye una nueva
comprobación inmediatamente antes de instalar.

### Herramientas disponibles

| Herramienta | Resultado |
|---|---|
| winget | `1.29.280`; consulta de paquetes operativa |
| Chocolatey | Detectado; no se consultó ni utilizó para instalar |
| Git | `2.54.0.windows.1` |
| Python | `3.14.5`, 64 bits, mediante `py -3.14` |
| VS Code | `1.133.0`, 64 bits |

## 2. Versión objetivo y fuente

### Objetivo aprobado y resolución de la discrepancia

La versión mayor aprobada es **PostgreSQL 18 x64**. La revisión menor no queda congelada en este
documento: deberá ser la minor estable vigente que muestre la política oficial de PostgreSQL justo
antes de descargar. Nunca se aceptarán beta, release candidate, snapshot ni versiones de desarrollo.

La discrepancia que originó esta revisión fue real y debía bloquear la instalación:

- una consulta anterior de fuentes oficiales mostraba PostgreSQL **18.4** como minor estable;
- winget reportó después el paquete **18.6-1**;
- los metadatos de winget, por sí solos, no demuestran una publicación oficial de PostgreSQL y no
  autorizaban instalar 18.6.

La revalidación del 2026-08-17 resolvió esa diferencia mediante fuentes primarias: la política
oficial identifica ahora **PostgreSQL 18.6** como minor estable vigente, y las release notes
oficiales confirman su publicación el 2026-08-13. Esas notas explican además que 18.5 no llegó a
publicarse por una regresión detectada antes del lanzamiento. Por tanto, 18.4 fue la referencia
estable anterior, pero ya no es la referencia actual. La referencia observada al cerrar este plan
es 18.6 y deberá comprobarse otra vez inmediatamente antes de cualquier descarga.

La consulta de solo lectura de winget encontró:

- paquete: `PostgreSQL.PostgreSQL.18`;
- versión del paquete: `18.6-1`;
- editor declarado: PostgreSQL Global Development Group;
- instalador x64 declarado: `postgresql-18.6-1-windows-x64.exe` alojado por EnterpriseDB;
- SHA-256 publicado en el manifiesto consultado:
  `cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1`.

El publicador, la URL y el hash anteriores siguen siendo únicamente declaraciones del manifiesto
de winget y no constituyen prueba oficial de publicación. El archivo local se descargó después desde
el origen oficial y se validó independientemente por tamaño, SHA-256, firma Authenticode y Microsoft
Defender. La evidencia completa está en
[`POSTGRESQL_INSTALLER_VERIFICATION.md`](POSTGRESQL_INSTALLER_VERIFICATION.md).

### Fuente propuesta

La prueba de publicación será la [política oficial de versiones de PostgreSQL](https://www.postgresql.org/support/versioning/)
y las release notes oficiales de la minor elegida. La fuente del binario será la
[página oficial de instaladores para Windows de PostgreSQL](https://www.postgresql.org/download/windows/),
que enlaza el instalador certificado y alojado por EnterpriseDB para las versiones soportadas. No
se usará un mirror, un instalador de terceros ni Chocolatey. Winget será solo una referencia
secundaria y nunca sustituirá la publicación oficial ni la validación local de la firma y el hash.

### Compuerta obligatoria antes de instalar

Esta secuencia no puede omitirse ni agruparse con la instalación:

1. Verificar en PostgreSQL.org cuál es la minor estable vigente de PostgreSQL 18.
2. Obtener el instalador únicamente desde la ruta oficial PostgreSQL → EDB, en una tarea autorizada.
3. Comprobar localmente firma digital, cadena de confianza y SHA-256 del archivo exacto.
4. Presentar versión, URL final, publicador, resultado de firma y SHA-256 al usuario.
5. Solicitar y recibir autorización humana expresa para ejecutar ese archivo exacto.
6. Solamente entonces iniciar el instalador; cualquier cambio de archivo, versión, URL o hash
   invalida la autorización y obliga a repetir la compuerta.

### Compatibilidad del DDL y la aplicación futura

- El contrato exige PostgreSQL 16 o superior; la versión mayor 18 lo satisface.
- `GENERATED ALWAYS AS (...) STORED` está soportado y coincide con las columnas generadas del DDL.
- `UNIQUE NULLS NOT DISTINCT` está soportado. El DDL v0.2 actual no depende de esa cláusula, pero
  una evolución futura compatible puede utilizarla.
- Las FKs simples/compuestas, checks, índices B-tree, índices parciales y JSONB utilizados son
  funcionalidades estables de PostgreSQL.
- FastAPI no fija una versión del servidor. SQLAlchemy y Alembic operan con PostgreSQL mediante un
  driver compatible; sus versiones concretas y la compatibilidad del driver con Python 3.14 se
  validarán en una tarea posterior, sin cambiar la selección del motor.
- Las ramas 17 y 16 solo serían alternativas ante una incompatibilidad verificable del ecosistema.
  No se hará ese cambio sin actualizar y aprobar este plan.

Referencias oficiales: [política de versiones](https://www.postgresql.org/support/versioning/),
[release notes de PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/),
[columnas generadas](https://www.postgresql.org/docs/18/ddl-generated-columns.html) y
[constraints](https://www.postgresql.org/docs/18/ddl-constraints.html).

## 3. Componentes y topología local propuesta

### Componentes

1. Instalar únicamente el servidor PostgreSQL 18 y sus herramientas de línea de comandos.
2. No instalar StackBuilder.
3. Aplazar pgAdmin a una tarea posterior. `psql` permite validar el servidor y el DDL con menos
   componentes y menor superficie de actualización. Si la operación diaria demuestra que la GUI
   aporta valor, se revisará e instalará por separado.

### Red y servicio

| Elemento | Propuesta |
|---|---|
| Puerto primario | `5432`, libre durante el diagnóstico |
| Alternativa | `5433`, solo si 5432 deja de estar libre; registrar el cambio en `.env` local |
| Escucha | `listen_addresses = 'localhost'` |
| Acceso | Solo `127.0.0.1/32` y `::1/128`; sin acceso LAN/Internet |
| Firewall | No crear ni ampliar reglas de entrada |
| Servicio esperado | `postgresql-x64-18`; confirmar el nombre real antes de usarlo |
| Inicio | Automático, condicionado a la validación posterior del servicio |

### Rutas propuestas, todavía inexistentes

| Uso | Ruta propuesta |
|---|---|
| Binarios | `C:\Program Files\PostgreSQL\18` |
| Datos del clúster | `C:\PerfectCatalogData\postgresql\18\data` |
| Respaldos | `C:\PerfectCatalogData\postgresql\18\backups` |
| Medios/imágenes futuras | `C:\PerfectCatalogData\media` |
| Logs del servidor | `C:\PerfectCatalogData\postgresql\18\logs` |

`C:\PerfectCatalogData` queda fuera de `C:\PERFECT_CATALOG`, por lo que datos, respaldos, medios
y logs operativos no estarán dentro del repositorio. Las carpetas solo se crearán después de la
aprobación, con permisos limitados a la cuenta del servicio y a los administradores necesarios.

## 4. Configuración inicial propuesta

### Datos, locale y tiempo

- Codificación de datos: `UTF8`.
- Locale de presentación: español de Panamá.
- Proveedor de locale aprobado para `perfect_catalog_dev`: ICU.
- ICU locale aprobado: `es-PA`.
- La collation predeterminada de la base será determinista. `Spanish_Panama.1252` no se utilizará
  como collation definitiva de la base del proyecto.
- `DateStyle = 'ISO, YMD'` para intercambios no ambiguos.
- `TimeZone = 'UTC'` en el servidor y las conexiones técnicas.
- `America/Panama` se usará en la capa de presentación. `timestamptz` conserva el instante y se
  interpreta internamente en UTC; la zona de presentación se aplica al mostrarlo.
- La zona horaria configurada en Odoo sigue pendiente. No se inferirá de Windows ni se convertirán
  todavía los seriales 1900/1904 del Excel.
- Los checksums de páginas de datos permanecerán habilitados. PostgreSQL 18 los habilita por
  defecto; no se usará `--no-data-checksums` y se validará posteriormente con `SHOW data_checksums`.

El instalador gráfico podría inicializar el clúster con un locale de Windows. Ese locale del
clúster no se aceptará como collation definitiva de `perfect_catalog_dev`. Una vez creado el rol
propietario y con autorización específica, la base deberá crearse explícitamente desde `template0`
con el siguiente comando propuesto, que **no se ejecuta en esta tarea**:

```sql
CREATE DATABASE perfect_catalog_dev
    WITH OWNER = perfect_catalog_owner
         TEMPLATE = template0
         ENCODING = 'UTF8'
         LOCALE_PROVIDER = icu
         ICU_LOCALE = 'es-PA';
```

La base predeterminada creada así utiliza una collation ICU determinista. La futura validación
propuesta será:

```sql
SELECT
    datname,
    pg_encoding_to_char(encoding) AS encoding,
    datlocprovider,
    datlocale AS icu_locale,
    datcollversion
FROM pg_database
WHERE datname = 'perfect_catalog_dev';

SHOW data_checksums;
SHOW TimeZone;
```

Los valores esperados son `UTF8`, proveedor `i` (ICU), locale `es-PA`, checksums `on` y zona
horaria `UTC`. La versión de collation registrada también deberá conservarse como evidencia.

La insensibilidad a mayúsculas y acentos para búsquedas se implementará posteriormente mediante
collations de búsqueda explícitas y/o normalización versionada. No se cambiará la igualdad exacta
ni la identidad de las referencias internas para hacer una búsqueda insensible.

### Conexiones y memoria conservadora

Para una estación compartida de 31.43 GiB, se propone inicialmente:

| Parámetro | Valor inicial |
|---|---:|
| `max_connections` | `30` |
| `shared_buffers` | `1GB` |
| `effective_cache_size` | `8GB` |
| `work_mem` | `8MB` |
| `maintenance_work_mem` | `256MB` |

Los demás parámetros de WAL, checkpoint y planner permanecerán en sus valores predeterminados.
Estos valores no son una optimización definitiva: se medirán con cargas sintéticas y se cambiarán
solo con evidencia. `work_mem` se aplica por operación, por lo que no debe elevarse globalmente sin
considerar concurrencia.

### Autenticación y contraseñas

- `password_encryption = 'scram-sha-256'`.
- `pg_hba.conf` admitirá solo host local IPv4/IPv6 con `scram-sha-256`; no se usará `trust`.
- Cada rol con login tendrá una contraseña distinta, aleatoria y de al menos 20 caracteres,
  generada/guardada por el usuario en un gestor de contraseñas.
- Las contraseñas se introducirán de forma interactiva; nunca como argumentos visibles, texto de
  documentación, consola capturada, screenshots o commits.
- `.env` contendrá secretos solo localmente y ya está ignorado por Git. `.env.example` deberá
  contener únicamente nombres y marcadores, nunca valores reales.

### Logging y rotación

- `logging_collector = on`, destino `stderr` y logs en la ruta operativa propuesta.
- Archivo diario con fecha, rotación cada 1 día o 100 MB, lo que ocurra primero.
- Conservar inicialmente 30 días; la eliminación posterior será una tarea controlada y limitada a
  la ruta exacta de logs, nunca un borrado recursivo amplio.
- Registrar conexiones, desconexiones, checkpoints y consultas de al menos 1000 ms.
- No usar `log_statement = 'all'`: podría registrar datos empresariales o secretos.

### Respaldos y restauración

- Antes de cada migración, crear `pg_dump` en formato custom dentro del directorio de respaldos,
  calcular SHA-256 y conservar un manifiesto con versión del servidor, fecha y base.
- Verificar cada respaldo con `pg_restore --list` y realizar restauraciones periódicas en una base
  temporal vacía autorizada. Un archivo existente no se sobrescribirá.
- El respaldo lógico será la estrategia inicial. Una política física/PITR se evaluará solo cuando
  exista volumen y criticidad reales.
- La restauración nunca se probará sobre `perfect_catalog_dev` ni sobre otra base existente.

## 5. Roles y base futuros

Base de desarrollo propuesta: `perfect_catalog_dev`.

| Rol | Propósito y privilegios futuros |
|---|---|
| `postgres` | Superusuario administrativo del motor. Solo instalación, recuperación y operaciones excepcionales. |
| `perfect_catalog_owner` | Propietario de la base/schema/objetos y login exclusivo para migraciones; sin superusuario. |
| `perfect_catalog_app` | Login futuro de FastAPI; DML estrictamente necesario, sin DDL ni administración. |
| `perfect_catalog_readonly` | Login de consulta/soporte; solo `CONNECT`, `USAGE` y `SELECT` aprobados. |

Reglas obligatorias:

- FastAPI nunca se conectará como `postgres` ni como `perfect_catalog_owner`.
- Aplicar mínimo privilegio y separar administración, propiedad/migración, aplicación y lectura.
- `postgres` creará inicialmente la base con `perfect_catalog_owner` como propietario; después el
  superusuario no se usará en el flujo normal.
- Los privilegios de tablas futuras y los `ALTER DEFAULT PRIVILEGES` se probarán con datos
  sintéticos antes de permitir una conexión de aplicación.
- No se crearán roles ni base hasta completar la compuerta y autorizar expresamente otra tarea.

## 6. Procedimiento futuro de instalación — no ejecutar ahora

Leyenda: **Usuario** decide o introduce secretos; **Elevación** requiere UAC; **Codex** puede
automatizar después de autorización; **Verificación** es de solo lectura tras cada acción.

1. **Usuario + Verificación:** confirmar en PostgreSQL.org la minor estable vigente de la rama 18
   y sus release notes; winget no es prueba suficiente.
2. **Codex:** consultar nuevamente `PostgreSQL.PostgreSQL.18` solo como contraste y presentar
   cualquier diferencia antes de continuar.
3. **Usuario + Codex:** autorizar en una tarea separada la obtención del instalador desde el enlace
   oficial PostgreSQL → EDB y calcular su SHA-256 sin ejecutarlo.
4. **Usuario + Verificación:** comprobar la firma Authenticode, cadena de confianza, publicador,
   URL final y SHA-256; presentar toda la evidencia y solicitar autorización expresa para ejecutar.
5. **Codex:** crear un punto de control documental: Git limpio, hash del DDL/Excel, inventario de
   software/servicios, puertos, espacio y rutas existentes. Un punto de restauración de Windows,
   si se desea y la política lo permite, requiere **Elevación** y aprobación específica.
6. **Usuario:** confirmar que la autorización se refiere al archivo exacto ya verificado; generar y guardar
   las contraseñas fuera de Git.
7. **Elevación:** iniciar el instalador validado mediante UAC. No ejecutar otra copia ni un binario
   con hash distinto.
8. **Usuario:** seleccionar solo PostgreSQL Server y Command Line Tools; excluir pgAdmin y
   StackBuilder en esta fase.
9. **Usuario:** indicar el directorio de binarios y el directorio de datos aprobados. El instalador
   podrá crear únicamente las rutas exactas autorizadas.
10. **Usuario:** introducir de forma interactiva la contraseña del superusuario `postgres`; no
   mostrarla ni capturarla.
11. **Usuario:** seleccionar puerto 5432 si la revalidación continúa libre; si está ocupado,
    detenerse y aprobar explícitamente 5433 antes de continuar.
12. **Usuario:** conservar los checksums habilitados. El cluster gráfico puede usar locale de
    Windows; la base del proyecto se creará después desde `template0` con ICU `es-PA`.
13. **Elevación:** permitir el registro exclusivo del servicio esperado `postgresql-x64-18` con
    inicio automático. No crear reglas de firewall externas.
14. **Verificación:** confirmar versión, firma de binarios, servicio, cuenta del servicio, rutas y
    que solo `localhost:5432` —o la alternativa aprobada— esté escuchando.
15. **Codex + Verificación:** comprobar `psql --version`, conexión local cifrada con SCRAM,
    checksums, zona UTC, parámetros de memoria y logs; probar que una IP no loopback no acepta conexión.
16. **Usuario + Codex:** crear posteriormente los cuatro roles mediante entrada interactiva de
    secretos y verificar que FastAPI no pueda usar el superusuario.
17. **Codex:** crear posteriormente `perfect_catalog_dev` desde `template0`, con propietario
    `perfect_catalog_owner`, UTF8, proveedor ICU y locale `es-PA`; ejecutar la consulta documental
    de validación antes de continuar.
18. **Codex + Verificación:** recalcular el hash del DDL y ejecutarlo en una única transacción solo
    después de una autorización específica; nunca mediante una sesión apuntando a otra base.
19. **Codex + Verificación:** confirmar exactamente 24 tablas bajo `perfect_catalog`, constraints,
    FKs e índices; probar inserts válidos/inválidos y rollback con datos sintéticos.
20. **Codex + Verificación:** crear el primer respaldo lógico, verificar su lista y ensayar una
    restauración en otra base vacía autorizada.
21. **Codex:** conservar evidencia sin secretos, actualizar continuidad y crear un commit de
    documentación. La instalación y sus resultados no deben versionar datos operativos.

## 7. Plan de recuperación

1. Si el instalador falla o solicita una decisión no documentada, cancelar y no reintentar a ciegas.
2. Conservar el log exacto del instalador, código de error, hora y hash del binario sin publicar
   contraseñas. No limpiar temporales hasta terminar el diagnóstico.
3. Detectar una instalación parcial comparando Apps instaladas, servicio exacto, procesos, puertos,
   claves PostgreSQL, binarios y cada ruta aprobada. No asumir que todos los componentes pertenecen
   a la misma instancia.
4. No detener, cambiar ni desinstalar otra versión/instancia. Identificar versión, nombre de servicio,
   ejecutable y `data_directory` antes de cualquier acción.
5. Si la instancia nueva existe, detener únicamente su servicio exacto mediante una acción elevada y
   aprobada. No matar procesos por patrón general.
6. Desinstalar únicamente la minor aprobada de PostgreSQL 18 mediante su desinstalador registrado.
   No usar borrado manual para sustituir la desinstalación.
7. Tratar datos, backups y logs por separado del binario. Antes de eliminar una ruta, resolverla a su
   ruta absoluta, confirmar que comienza exactamente en `C:\PerfectCatalogData\postgresql\18\` y
   obtener aprobación específica. Conservarla por defecto para análisis.
8. Restaurar solo los parámetros previamente documentados. Como este plan no modifica PATH,
   firewall ni políticas, no debería existir nada que revertir en esos ámbitos.
9. Repetir `git status`, hashes del DDL y del Excel y pruebas del proyecto para confirmar que la
   instalación no alteró `C:\PERFECT_CATALOG`.
10. Si existe cualquier duda de pertenencia de un archivo, servicio o clave, detener la recuperación
    y solicitar intervención del usuario; nunca ampliar el objetivo de eliminación.

## 8. Checklist de autorización previa

- [x] Versión mayor aprobada: PostgreSQL 18 x64.
- [x] Minor estable reconfirmada en PostgreSQL.org inmediatamente antes de descargar: 18.6 al 2026-08-17.
- [x] Fuente oficial definida: PostgreSQL para Windows → instalador EDB.
- [x] Firma/hash del instalador verificados contra el archivo descargado.
- [x] Versión, URL, publicador, firma y SHA-256 documentados para revisión del usuario.
- [x] Puerto libre confirmado: 5432 y 5433 sin listener al 2026-08-17; revalidar inmediatamente antes.
- [x] Directorio de datos aprobado como propuesta futura.
- [x] Directorio de respaldos aprobado como propuesta futura.
- [x] Directorio de imágenes aprobado como propuesta futura.
- [x] UTF8, ICU `es-PA` y collation determinista aprobados para `perfect_catalog_dev`.
- [x] Checksums de datos habilitados como decisión de instalación.
- [ ] Política de contraseña comprendida.
- [x] Roles futuros aprobados.
- [x] Base de desarrollo `perfect_catalog_dev` aprobada.
- [ ] Plan de recuperación revisado.
- [x] DDL v0.2 y hash confirmados: `8602d170e3345c9694bd498bd9f23162b72bd740e582fa3caa6a2bad3a1d660c`.
- [ ] Autorización expresa del usuario para instalar.

## 9. Decisiones que continúan abiertas

- autorización humana expresa para ejecutar ese instalador después de presentar la evidencia;
- aprobación operativa final de política de logs y memoria inicial;
- selección privada de contraseñas y aceptación del UAC por el usuario;
- zona horaria real de Odoo y sistema de fechas 1900/1904 del Excel;
- versiones futuras de FastAPI, SQLAlchemy, Alembic y driver compatibles con Python 3.14.

El siguiente paso autorizado es revisar la evidencia de
[`POSTGRESQL_INSTALLER_VERIFICATION.md`](POSTGRESQL_INSTALLER_VERIFICATION.md) y solicitar
autorización humana expresa para ejecutar ese archivo exacto. Instalar, crear roles/base o ejecutar
SQL exige una solicitud posterior y expresa.
