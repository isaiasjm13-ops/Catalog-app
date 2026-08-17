# Plan de remediación de la instalación PostgreSQL 18.6

> **Estado al 2026-08-17:** la aplicación desviada fue desinstalada mediante la entrada registrada
> de Windows. El cluster residual permanece intacto. Este documento no autoriza limpiar restos,
> reinstalar, borrar, mover, ejecutar SQL ni modificar datos.

## 1. Alcance y evidencia previa

La instalación funcional de PostgreSQL 18.6 no coincidió con el plan aprobado. Antes de contenerla
se comprobó la identidad exacta:

| Elemento | Valor previo |
|---|---|
| Servicio | `postgresql-x64-18` |
| Estado | `Running` |
| Inicio | `Auto` |
| PID del servicio `pg_ctl.exe` | `39744` |
| PID principal `postgres.exe` | `47416` |
| Cuenta | `NT AUTHORITY\NetworkService` |
| Ejecutable | `C:\Program Files\PostgreSQL\18\bin\pg_ctl.exe` |
| Argumento de datos | `-D "C:\Program Files\PostgreSQL\18\data"` |
| Listeners | `0.0.0.0:5432` y `[::]:5432`, propiedad del PID `47416` |
| LAN | `192.168.0.128:5432 - aceptando conexiones` mediante `pg_isready` |

No había otro servicio PostgreSQL. Git conservaba los cuatro cambios documentales de la
instalación desviada y HEAD era `bf4d32c Verify PostgreSQL 18.6 installer artifact`.

## 2. Desviaciones y riesgos

| Desviación | Evidencia | Riesgo |
|---|---|---|
| Datos fuera de la ruta aprobada | Cluster en `C:\Program Files\PostgreSQL\18\data`; ruta `C:\PerfectCatalogData\postgresql\18\data` ausente | Mezcla binarios/datos, permisos y recuperación distintos del diseño operativo |
| Escucha en todas las interfaces | `listen_addresses = '*'`; listeners IPv4/IPv6 comodín y respuesta en LAN | Superficie de red innecesaria, aunque HBA limite autenticación a loopback |
| Locale inconsistente | Usuario reportó Panamá; `lc_*` muestra `Spanish_Spain.1252` | Presentación regional no validada y riesgo de asumir una collation incorrecta |
| Stack Builder presente/abierto | `bin\stackbuilder.exe` existe y fue ejecutado accidentalmente | Superficie adicional y posibilidad de instalar complementos no aprobados |

`pg_hba.conf` conservaba reglas host exclusivamente para `127.0.0.1/32` y `::1/128` mediante
SCRAM-SHA-256. Esto redujo el acceso, pero no corrigió la escucha de red.

## 3. Contención aplicada

Con autorización humana expresa y UAC, se administró únicamente `postgresql-x64-18`:

1. parada ordenada mediante el administrador de servicios de Windows;
2. espera hasta estado `Stopped`;
3. cambio de inicio de `Auto` a `Manual`.

No se usó terminación forzada. La primera invocación elevada no produjo cambios por un problema
de escape del comando; la verificación inmediata confirmó `Running/Auto`. Se repitió correctamente
y se exigió evidencia posterior, sin efectos parciales ni procesos eliminados a la fuerza.

| Verificación posterior | Resultado |
|---|---|
| Servicio | `postgresql-x64-18` |
| Estado | `Stopped` |
| Inicio | `Manual` |
| PID | `0` |
| Procesos `postgres.exe` | Ninguno |
| Listeners en 5432 | Ninguno |
| `pg_isready -h localhost -p 5432` | `sin respuesta`, salida `2` |
| `pg_isready -h 192.168.0.128 -p 5432` | `sin respuesta`, salida `2` |
| Otros servicios PostgreSQL | Ninguno |

No se modificaron `postgresql.conf`, `pg_hba.conf`, firewall, PATH ni archivos del cluster.

## 4. Entrada oficial de desinstalación

La entrada registrada de Windows se inspeccionó sin ejecutarla:

| Elemento | Valor |
|---|---|
| Nombre mostrado | `PostgreSQL 18` |
| Versión | `18.6-1` |
| Publicador | `PostgreSQL Global Development Group` |
| Ubicación instalada | `C:\Program Files\PostgreSQL\18` |
| Desinstalador | `C:\Program Files\PostgreSQL\18\uninstall-postgresql.exe` |
| Comando registrado | `"C:\Program Files\PostgreSQL\18\uninstall-postgresql.exe"` |
| Desinstalación silenciosa registrada | No |

El archivo no tenía firma Authenticode. Antes de usarlo se validaron la entrada/ruta exactas,
estructura PE, ausencia de reparse point, fechas, SHA-256
`3d5d7393cb00b6eb00fae3f92d55ab566258fc20da7e6c1be1b91f2f52171194`, propietario
`BUILTIN\Administradores`, ACL de solo lectura/ejecución para usuarios estándar y un escaneo
Microsoft Defender con 0 detecciones. Se invocó exclusivamente desde Programas y características,
no directamente.

## 5. Componentes antes de desinstalar y cluster preservado

| Componente | Estado detectado |
|---|---|
| PostgreSQL Server | Presente: `bin\postgres.exe` |
| Command Line Tools | Presentes: `bin\psql.exe` |
| Stack Builder | Presente: `bin\stackbuilder.exe`; no está ejecutándose |
| pgAdmin 4 | No detectado |
| Complementos de Stack Builder | No detectados en programas registrados ni como instaladores recientes en sus ubicaciones habituales |

El directorio incorrecto `C:\Program Files\PostgreSQL\18\data` mide `41,903,499` bytes y contiene
`976` archivos según metadata. No se inspeccionó ni expuso el contenido de esos archivos.

Según el historial controlado de esta instalación, no se ejecutó SQL, no se importó el Excel y
no se crearon bases, roles o tablas del proyecto. Por tanto, no existe información empresarial en
PostgreSQL atribuible a este proceso. Aun así, el cluster se preservará temporalmente y no se
borrará hasta que una comprobación futura autorizada confirme esa ausencia.

## 6. Procedimiento de remediación y estado

1. **Completado:** obtener autorización humana expresa para desinstalar PostgreSQL 18.6 mediante la interfaz
   gráfica oficial.
2. **Completado:** reconfirmar servicio `Stopped/Manual`, ausencia de listeners, Git y hashes protegidos.
3. **Completado:** abrir Programas y características de Windows e iniciar `Uninstall/Change` desde
   la entrada registrada; el usuario atendió UAC y eligió `Entire application`. No se ejecutó el
   archivo directamente ni se usó modo silencioso.
4. **Completado:** desinstalar los binarios y el servicio de PostgreSQL 18.6. No seleccionar ni aceptar ninguna
   opción que borre datos sin una autorización adicional y específica.
5. **Completado:** verificar que servicio, binarios y listeners desaparecieron. Preservar temporalmente
   `C:\Program Files\PostgreSQL\18\data` si el desinstalador lo conserva.
6. **Pendiente:** confirmar por un mecanismo seguro y sin contraseñas expuestas que el cluster no contiene datos
   empresariales. Solo entonces preparar una compuerta separada para su eliminación exacta.
7. **Pendiente:** revalidar el mismo instalador PostgreSQL 18.6 por SHA-256 y Authenticode antes de reinstalar.
8. **Pendiente:** reinstalar interactivamente y seleccionar exclusivamente PostgreSQL Server y Command Line
   Tools; desmarcar pgAdmin y Stack Builder y no iniciar complementos al finalizar.
9. **Pendiente:** usar binarios en `C:\Program Files\PostgreSQL\18` y datos en
   `C:\PerfectCatalogData\postgresql\18\data`.
10. **Pendiente:** antes de crear bases, validar servicio, cuenta, ruta `-D`, inicio, puerto y locale. Exigir
    escucha exclusiva en `127.0.0.1` y `::1`; si el instalador vuelve a usar `*`, detener el servicio
    y abrir una compuerta específica para corregir `listen_addresses`.
11. **Pendiente:** verificar HBA local con SCRAM, ausencia de respuesta LAN, PATH sin cambios y opciones ICU.
12. **Pendiente:** solo después de una validación conforme, solicitar autorización independiente para crear roles
    y `perfect_catalog_dev` desde `template0` con UTF8, proveedor ICU y locale `es-PA`.

## 7. Protecciones vigentes y siguiente compuerta

- PostgreSQL 18.6 ya no aparece instalado; servicio, binarios y listeners fueron retirados.
- El cluster residual `C:\Program Files\PostgreSQL\18\data` permanece intacto.
- No se reinstaló ni se limpiaron/movieron manualmente restos.
- No se modificó contenido del cluster.
- No se ejecutó SQL, DDL ni Stack Builder; el desinstalador se inició solamente desde la entrada
  registrada de Windows y ya fue retirado.
- No se solicitaron ni usaron contraseñas.
- El Excel maestro y el DDL no fueron modificados.

La siguiente compuerta pendiente es la **inspección, cuarentena y limpieza exacta de restos** antes
de reinstalar. Requiere autorización humana separada; esta documentación no permite borrar ni mover
el cluster o los logs potencialmente sensibles.
