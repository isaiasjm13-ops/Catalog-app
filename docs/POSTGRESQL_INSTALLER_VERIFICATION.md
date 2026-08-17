# Verificación del instalador de PostgreSQL 18.6 x64

> **Estado:** artefacto descargado y verificado el 2026-08-17. El archivo no fue ejecutado y esta
> verificación no autoriza instalar PostgreSQL ni ningún componente adicional.

## 1. Publicación y origen

| Elemento | Evidencia |
|---|---|
| Fecha y hora de verificación | 2026-08-17 13:39:04 a 13:39:04, UTC-05:00 (`America/Panama`) |
| Versión | PostgreSQL 18.6, paquete de instalador `18.6-1` |
| Arquitectura | Windows x64 |
| Publicación oficial | PostgreSQL 18.6 estable, publicada el 2026-08-13 |
| Cadena de origen | PostgreSQL para Windows → instalador certificado alojado por EnterpriseDB |
| URL final | `https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64.exe` |
| Contraste de winget | `PostgreSQL.PostgreSQL.18`, versión `18.6-1`, editor declarado `PostgreSQL Global Development Group` |

Fuentes consultadas: [política oficial de versiones de PostgreSQL](https://www.postgresql.org/support/versioning/),
[release notes oficiales de PostgreSQL 18.6](https://www.postgresql.org/docs/release/18.6/),
[página oficial de PostgreSQL para Windows](https://www.postgresql.org/download/windows/) y
[página de descargas de EnterpriseDB](https://www.enterprisedb.com/downloads/postgres-postgresql-downloads).
La página oficial de Windows remite a EnterpriseDB; la URL exacta declarada por winget pertenece
a ese distribuidor y respondió por HTTPS con `200 OK`, tipo
`application/x-msdos-program`, tamaño `375833688` y fecha de origen 2026-08-13.

Los metadatos de winget se usaron solo como contraste. La prueba de publicación es PostgreSQL.org,
y la aceptación del archivo local depende de las comprobaciones independientes que siguen.

## 2. Archivo local

| Elemento | Valor |
|---|---|
| Ruta absoluta | `C:\Users\Diseño2\Downloads\PerfectCatalog\PostgreSQL\18.6\postgresql-18.6-1-windows-x64.exe` |
| Nombre | `postgresql-18.6-1-windows-x64.exe` |
| Tamaño | `375833688` bytes |
| Creación local | 2026-08-17 13:19:10.9075285, UTC-05:00 |
| Finalización de descarga | 2026-08-17 13:38:20.6393099, UTC-05:00 |
| Ubicación respecto de Git | Fuera de `C:\PERFECT_CATALOG`; no versionado |

Solo se creó el directorio de descarga autorizado. No se creó `C:\PerfectCatalogData` ni
ninguno de los futuros directorios operativos de datos, backups, logs o medios.

## 3. Integridad SHA-256

| Comprobación | Resultado |
|---|---|
| SHA-256 esperado | `cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1` |
| SHA-256 obtenido | `cae561e98d09f3f4a1a95759249240f86f66d71dcf33d14b6f7be894078401d1` |
| Coincidencia exacta | **Sí** |

El hash se calculó localmente con `Get-FileHash -Algorithm SHA256` después de que terminó la
transferencia y el proceso de descarga liberó el archivo.

## 4. Firma Authenticode

La firma se verificó con `Get-AuthenticodeSignature`, sin ejecutar el instalador.

| Elemento | Resultado |
|---|---|
| Estado | `Valid` |
| Mensaje nativo | `Firma comprobada.` |
| Tipo | `Authenticode` |
| Firmante | `CN=EnterpriseDB Corporation, O=EnterpriseDB Corporation, L=Wilmington, S=Delaware, C=US` |
| Emisor | `CN=DigiCert Trusted G4 Code Signing RSA4096 SHA384 2021 CA1, O="DigiCert, Inc.", C=US` |
| Vigencia del firmante | 2026-01-29 19:00:00 a 2029-01-31 18:59:59, UTC-05:00 |
| Huella del firmante | `7BEDD1269FCCF7A5D95F18274750B79893C06C70` |
| Certificado de sello de tiempo | `CN=DigiCert SHA256 RSA4096 Timestamp Responder 2025 1, O="DigiCert, Inc.", C=US` |
| Emisor del sello | `CN=DigiCert Trusted G4 TimeStamping RSA4096 SHA256 2025 CA1, O="DigiCert, Inc.", C=US` |
| Vigencia del certificado de sello | 2025-06-03 19:00:00 a 2036-09-03 18:59:59, UTC-05:00 |
| Huella del sello | `DD6230AC860A2D306BDA38B16879523007FB417E` |

La herramienta nativa expuso el certificado de sello de tiempo y su vigencia, pero no mostró el
instante exacto del sellado como propiedad separada. El firmante corresponde al distribuidor
oficial esperado, EnterpriseDB Corporation.

## 5. Microsoft Defender

Se ejecutó `Start-MpScan -ScanType CustomScan` exclusivamente contra el archivo descargado.

| Elemento | Resultado |
|---|---|
| Microsoft Defender Antivirus | Habilitado |
| Protección en tiempo real | Habilitada |
| Versión de firmas | `1.457.209.0` |
| Última actualización de firmas | 2026-08-17 04:07:54, UTC-05:00 |
| Comando de escaneo | Completado sin error |
| Detecciones antes | `0` |
| Detecciones después | `0` |
| Detecciones asociadas al archivo | `0` |

Resultado: no se registraron amenazas para el instalador verificado.

## 6. Estado seguro posterior

- El `.exe` no fue ejecutado.
- No se instaló PostgreSQL, pgAdmin, Stack Builder ni ningún otro software.
- No existe el servicio `postgresql-x64-18` ni otro servicio PostgreSQL detectado.
- `psql`, `pg_config`, `postgres`, `pg_ctl` y `pgadmin4` continúan ausentes.
- Los puertos 5432 y 5433 continúan sin listeners.
- No se crearon cluster, bases, roles, tablas, credenciales ni reglas de firewall.
- No se modificaron PATH, registro, variables del sistema, DDL ni Excel maestro.
- El instalador permanece fuera del repositorio y ningún `.exe` fue agregado a Git.

## 7. Siguiente compuerta pendiente

La verificación técnica del artefacto quedó completa. La instalación permanece bloqueada hasta
que el usuario revise esta evidencia y autorice de forma humana, expresa y separada la ejecución
del archivo exacto identificado por la ruta y SHA-256 anteriores. Cualquier cambio de archivo,
versión, URL, firma o hash invalida esta verificación y obliga a repetirla.
