# Consola web local de revisión

Estado: implementada y validada localmente. La revisión usa `0006` y el centro de ingreso usa la
migración `0007`. No se ha aplicado ni revisado ningún plan empresarial real.

## Separación de superficies

| Superficie | Dirección | Fuente | Mutaciones |
|---|---|---|---|
| Catálogo publicado | `http://127.0.0.1:8080/` (`INICIAR-CATALOGO-PUBLICADO.cmd`) | PostgreSQL, último release | Ninguna |
| Consola operativa | `http://127.0.0.1:8081/operator` | PostgreSQL | Ingreso y decisión individual |

`INICIAR-REVISOR.cmd` arranca otro proceso y otro puerto; no agrega rutas administrativas al catálogo
público. El visor XLSX del piloto (`INICIAR-SERVER.cmd`) se retiró por evadir cuarentena, dry-run y
aprobación.

La navegación **Ingresos** abre `http://127.0.0.1:8081/operator/intake`. Antes del primer uso se
debe ejecutar `ACTUALIZAR-SISTEMA.cmd`. El flujo y sus límites están documentados en
[`INTAKE_WORKFLOW.md`](INTAKE_WORKFLOW.md).

## Inicio seguro

Haz doble clic en `INICIAR-REVISOR.cmd`. La ventana sólo solicita la contraseña de
`perfect_catalog_app`, oculta y conservada en memoria. El iniciador usa la identidad de Windows como
actor auditable, genera un código web temporal aleatorio y abre
`http://127.0.0.1:8081/operator/login` en el navegador predeterminado.

Introduce allí el código mostrado en la consola, nunca la contraseña de PostgreSQL. El código no se
guarda en archivos ni se añade a la URL. Al cerrar la ventana se pierden clave de sesión, código y
sesiones activas. El inicio avanzado por CLI permite pedir actor y código manualmente cuando una
operación requiera una identidad distinta de la sesión de Windows.

## Flujo visible

- La portada enumera únicamente planes en estado `applied` que crearon identidades.
- Tras crear un dry-run, **Ingresos** enlaza una inspección que muestra UUID, cantidad de operaciones,
  versiones, hashes y fingerprint completos. **Verificar y preparar** registra aprobación y aplicación
  como eventos separados dentro de una sola transacción y una sola confirmación del operador.
- Cada plan muestra pendientes, aprobadas, rechazadas e inconsistentes.
- La cola usa 50 registros por página y consulta set-based; admite más de 25,000 sin cargar todo el
  catálogo en HTML ni ejecutar una consulta por producto.
- Se puede buscar por nombre, referencia original/normalizada o número de fila y filtrar por estado.
- Cada tarjeta muestra UUID, fila fuente, referencia, aplicaciones vehiculares, estados y
  `review_sha256` completo.
- Solo una identidad coherente y pendiente presenta botones. Aprobar o rechazar exige un motivo de
  4 a 500 caracteres y una confirmación explícita por ficha.
- El filtro `pending` ofrece además una decisión atómica para todo su resultado (máximo 500). El
  operador puede acotar por búsqueda y aprobar o rechazar con un motivo común; el servidor exige
  que el conteo siga idéntico y recalcula la evidencia individual antes de escribir cada auditoría.
- Tras la decisión se usa redirect-after-POST; refrescar no repite la escritura.
- Inconsistencias estructurales se muestran bloqueadas y deben investigarse fuera de la UI.

Cada transición vuelve a verificar el plan completo, fingerprint, archivo físico, identidad y hashes.
La aplicación usa una transacción serializable y la revisión continúa siendo estrictamente individual;
la web no implementa aprobación masiva de productos.

## Controles de seguridad

- El proceso rechaza `0.0.0.0` y cualquier host distinto de localhost.
- Código temporal derivado con PBKDF2-HMAC-SHA256; no se conserva el texto original.
- Máximo cinco intentos fallidos dentro de cinco minutos; reiniciar el proceso invalida sesiones.
- Sesión aleatoria firmada, `HttpOnly`, `SameSite=Strict`, limitada a una hora y revocable al salir.
- Challenge CSRF también para login; CSRF de sesión y verificación exacta de `Origin` en cada POST.
- Formularios únicamente URL-encoded, con campos no duplicados y tamaño total limitado.
- Jinja2 con autoescape y `StrictUndefined`; CSP, `frame-ancestors none`, `no-store`, `nosniff` y
  `Referrer-Policy: no-referrer`.
- Sin OpenAPI, endpoints JSON de catálogo, CORS, secretos en URL ni credenciales en `.env`.
- Las cargas usan multipart limitado, cuarentena content-addressed e historial append-only; no
  existe descarga, extracción, importación o publicación automática.

El uso es local, pero eso no reemplaza los controles: un navegador puede recibir solicitudes de
otros sitios aun cuando el servidor escuche solo en loopback.

## Estado esperado tras el dry-run

La portada indica que no hay planes aplicados hasta completar las dos decisiones explícitas desde
la inspección enlazada en **Ingresos**. La primera deja el plan en `approved`; la segunda lo lleva a
`applied` y habilita la cola. Ninguna de las dos publica el catálogo.
# Promoción individual de ingresos

La versión 1.2 añade en `/operator/intake` una acción individual para datos Odoo en cuarentena. Sólo
aparece tras aplicar la migración `0008` y nunca se ejecuta durante la recepción. Requiere los mismos
controles de sesión, Origin y CSRF de las decisiones, además de motivo y confirmación explícita.
El resultado es perfilado + dry-run en `awaiting_review`, no una aprobación ni un apply.
