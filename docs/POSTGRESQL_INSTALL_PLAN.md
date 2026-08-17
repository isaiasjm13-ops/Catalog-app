# Plan de preparación para PostgreSQL local

> **Estado al 2026-08-17:** diagnóstico completado y propuesta preparada. PostgreSQL no está
> instalado, este procedimiento no se ha ejecutado y todavía requiere aprobación expresa.

Este documento define la instalación local futura de PostgreSQL para Perfect Catalog. No autoriza
descargas, instalación, creación de servicios, directorios, roles, bases de datos ni ejecución del
DDL. Toda ruta y valor indicados son propuestas pendientes de la aprobación señalada en el checklist.

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

### Recomendación concreta

Se propone **PostgreSQL 18.6 x64**, publicado como versión estable el 2026-08-13. Es la minor
vigente de la rama 18, recibe soporte hasta el 2030-11-14 y ofrece el horizonte más largo de las
ramas estables disponibles para un proyecto nuevo. No se propone PostgreSQL 19 porque actualmente
es una versión beta.

La consulta de solo lectura de winget encontró:

- paquete: `PostgreSQL.PostgreSQL.18`;
- versión del paquete: `18.6-1`;
- editor declarado: PostgreSQL Global Development Group;
- instalador x64 declarado: `postgresql-18.6-1-windows-x64.exe` alojado por EnterpriseDB;
- SHA-256 publicado en el manifiesto consultado:
  `cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1`.

Ese hash es solo una referencia de metadatos: no está verificado contra un archivo local porque no
se descargó ningún instalador. Debe consultarse nuevamente y compararse con el archivo exacto antes
de la instalación.

### Fuente propuesta

La fuente primaria será la [página oficial de instaladores para Windows de PostgreSQL](https://www.postgresql.org/download/windows/),
que enlaza el instalador certificado y alojado por EnterpriseDB para las versiones soportadas. No
se usará un mirror, un instalador de terceros ni Chocolatey. Winget podrá servir como segunda
evidencia del identificador, versión, URL y hash, pero no sustituye la validación de la firma del
archivo descargado.

### Compatibilidad del DDL y la aplicación futura

- El contrato exige PostgreSQL 16 o superior; 18.6 lo satisface.
- `GENERATED ALWAYS AS (...) STORED` está soportado y coincide con las columnas generadas del DDL.
- `UNIQUE NULLS NOT DISTINCT` está soportado. El DDL v0.2 actual no depende de esa cláusula, pero
  una evolución futura compatible puede utilizarla.
- Las FKs simples/compuestas, checks, índices B-tree, índices parciales y JSONB utilizados son
  funcionalidades estables de PostgreSQL.
- FastAPI no fija una versión del servidor. SQLAlchemy y Alembic operan con PostgreSQL mediante un
  driver compatible; sus versiones concretas y la compatibilidad del driver con Python 3.14 se
  validarán en una tarea posterior, sin cambiar la selección del motor.
- PostgreSQL 17.11 y 16.15 siguen siendo alternativas estables si una incompatibilidad verificable
  del ecosistema obligara a retroceder. No se hará ese cambio sin actualizar y aprobar este plan.

Referencias oficiales: [política de versiones](https://www.postgresql.org/support/versioning/),
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

- Encoding del clúster y de `perfect_catalog_dev`: `UTF8`.
- Locale/collation propuesto en Windows: proveedor `libc`, `LC_COLLATE` y `LC_CTYPE`
  `Spanish_Panama.1252`. El instalador debe mostrar y aceptar exactamente ese locale; si no está
  disponible, se detendrá la instalación para revisar la alternativa, sin aceptar silenciosamente
  el valor predeterminado.
- `DateStyle = 'ISO, YMD'` para intercambios no ambiguos.
- `TimeZone = 'UTC'` en el servidor y las conexiones técnicas.
- `America/Panama` se usará en la capa de presentación. `timestamptz` conserva el instante y se
  interpreta internamente en UTC; la zona de presentación se aplica al mostrarlo.
- La zona horaria configurada en Odoo sigue pendiente. No se inferirá de Windows ni se convertirán
  todavía los seriales 1900/1904 del Excel.

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
- No se crearán roles ni base hasta aprobar este plan y autorizar expresamente otra tarea.

## 6. Procedimiento futuro de instalación — no ejecutar ahora

Leyenda: **Usuario** decide o introduce secretos; **Elevación** requiere UAC; **Codex** puede
automatizar después de autorización; **Verificación** es de solo lectura tras cada acción.

1. **Usuario + Verificación:** confirmar que 18.6 sigue siendo la minor estable vigente y que el
   instalador procede del enlace oficial de PostgreSQL hacia EDB.
2. **Codex:** consultar nuevamente los metadatos de `PostgreSQL.PostgreSQL.18`; descargar solo tras
   autorización separada y calcular SHA-256 del archivo sin ejecutarlo.
3. **Usuario + Verificación:** comparar hash con la fuente vigente y comprobar la firma Authenticode,
   cadena de confianza, nombre del editor y ausencia de advertencias.
4. **Codex:** crear un punto de control documental: Git limpio, hash del DDL/Excel, inventario de
   software/servicios, puertos, espacio y rutas existentes. Un punto de restauración de Windows,
   si se desea y la política lo permite, requiere **Elevación** y aprobación específica.
5. **Usuario:** aprobar versión, componentes, puerto, locale, rutas, roles y base; generar y guardar
   las contraseñas fuera de Git.
6. **Elevación:** iniciar el instalador validado mediante UAC. No ejecutar otra copia ni un binario
   con hash distinto.
7. **Usuario:** seleccionar solo PostgreSQL Server y Command Line Tools; excluir pgAdmin y
   StackBuilder en esta fase.
8. **Usuario:** indicar el directorio de binarios y el directorio de datos aprobados. El instalador
   podrá crear únicamente las rutas exactas autorizadas.
9. **Usuario:** introducir de forma interactiva la contraseña del superusuario `postgres`; no
   mostrarla ni capturarla.
10. **Usuario:** seleccionar puerto 5432 si la revalidación continúa libre; si está ocupado,
    detenerse y aprobar explícitamente 5433 antes de continuar.
11. **Usuario:** seleccionar `UTF8` y el locale exacto aprobado. Si no aparece, cancelar antes de
    inicializar el clúster y revisar el plan.
12. **Elevación:** permitir el registro exclusivo del servicio esperado `postgresql-x64-18` con
    inicio automático. No crear reglas de firewall externas.
13. **Verificación:** confirmar versión, firma de binarios, servicio, cuenta del servicio, rutas y
    que solo `localhost:5432` —o la alternativa aprobada— esté escuchando.
14. **Codex + Verificación:** comprobar `psql --version`, conexión local cifrada con SCRAM, encoding,
    locale, zona UTC, parámetros de memoria y logs; probar que una IP no loopback no acepta conexión.
15. **Usuario + Codex:** crear posteriormente los cuatro roles mediante entrada interactiva de
    secretos y verificar que FastAPI no pueda usar el superusuario.
16. **Codex:** crear posteriormente `perfect_catalog_dev`, con `perfect_catalog_owner` como
    propietario, encoding/locale aprobados y sin datos empresariales.
17. **Codex + Verificación:** recalcular el hash del DDL y ejecutarlo en una única transacción solo
    después de una autorización específica; nunca mediante una sesión apuntando a otra base.
18. **Codex + Verificación:** confirmar exactamente 24 tablas bajo `perfect_catalog`, constraints,
    FKs e índices; probar inserts válidos/inválidos y rollback con datos sintéticos.
19. **Codex + Verificación:** crear el primer respaldo lógico, verificar su lista y ensayar una
    restauración en otra base vacía autorizada.
20. **Codex:** conservar evidencia sin secretos, actualizar continuidad y crear un commit de
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
6. Desinstalar únicamente PostgreSQL 18.6 mediante su desinstalador registrado. No usar borrado manual
   para sustituir la desinstalación.
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

- [x] Versión estable confirmada: PostgreSQL 18.6 al 2026-08-17; revalidar el día de instalación.
- [x] Fuente oficial confirmada: PostgreSQL para Windows → instalador EDB; revalidar el enlace.
- [ ] Firma/hash del instalador verificados contra el archivo descargado.
- [x] Puerto libre confirmado: 5432 y 5433 sin listener al 2026-08-17; revalidar inmediatamente antes.
- [ ] Directorio de datos aprobado.
- [ ] Directorio de respaldos aprobado.
- [ ] Directorio de imágenes aprobado.
- [ ] Locale aprobado.
- [ ] Política de contraseña comprendida.
- [ ] Roles aprobados.
- [ ] Base de desarrollo aprobada.
- [ ] Plan de recuperación revisado.
- [x] DDL v0.2 y hash confirmados: `8602d170e3345c9694bd498bd9f23162b72bd740e582fa3caa6a2bad3a1d660c`.
- [ ] Autorización expresa del usuario para instalar.

## 9. Decisiones que continúan abiertas

- aprobación del objetivo PostgreSQL 18.6 y del aplazamiento de pgAdmin;
- aprobación de rutas, puerto alternativo, locale, política de logs y memoria inicial;
- aprobación de los roles y de `perfect_catalog_dev`;
- selección privada de contraseñas y aceptación del UAC por el usuario;
- zona horaria real de Odoo y sistema de fechas 1900/1904 del Excel;
- versiones futuras de FastAPI, SQLAlchemy, Alembic y driver compatibles con Python 3.14.

El siguiente paso autorizado es revisar este documento y completar las aprobaciones. Instalar,
crear roles/base o ejecutar SQL exige una solicitud posterior y expresa.
