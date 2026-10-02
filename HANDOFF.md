# HANDOFF.md - Estado de Traspasos Entre Sesiones

> El historial completo anterior (bloques 2026-08-17 a 2026-09-04, ~1.570 lineas) esta en
> [docs/HANDOFF-ARCHIVO-2026-09-04.md](docs/HANDOFF-ARCHIVO-2026-09-04.md). Este archivo es el
> resumen vigente; agrega aqui solo el estado actual y lo pendiente.

## Estado actual (2026-10-02)

- Rama de trabajo: `workflow-3-etapas` (21+ commits por delante de `master`, aun sin fusionar).
- Suite de pruebas: `.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"`
  -> 474 pruebas OK, 6 omitidas (necesitan Postgres real con `PERFECT_CATALOG_RUN_INTEGRATION=1`).
- Base de datos: migraciones 0017-0028 aplicadas (log del 2026-10-02); la 0029 (seleccion manual de fotos) esta escrita y PENDIENTE de aplicar con ACTUALIZAR-SISTEMA.cmd.
- No hay `.env`: la contrasena de Postgres se pide a mano (`--prompt-password`), nunca se guarda.

## Como arrancar

| Archivo | Que hace | Puerto por defecto |
|---|---|---|
| `INICIAR-REVISOR.cmd` | Consola del operador (Cargar, Revisar, Entregar, Administracion) | 8081 |
| `INICIAR-GENERADOR-PUBLICO.cmd` | Generador publico de catalogos | 8082 |
| `INICIAR-TODO.cmd` | Ambos; el revisor apunta al puerto real del publico | 8081 / 8082 |
| `ACTUALIZAR-SISTEMA.cmd` | Aplica migraciones pendientes (exige cerrar los servidores) | - |
| `LIMPIAR-IMPORTACIONES.cmd` | Borra importaciones (con respaldo; exige cerrar los servidores) | - |
| `RESPALDAR-BASE.cmd` | Respaldo manual de la base en `backups/` (pide la contrasena) | - |

Los lanzadores (`scripts/iniciar-servicio.ps1`, `scripts/iniciar-todo.ps1`) eligen puerto libre,
muestran la URL, avisan si Postgres esta apagado, reinician una instancia vieja del mismo servicio
y dejan rastro en `logs/operator-live.log` y `logs/public-live.log`. Los servidores mueren al
cerrar su ventana.

## Modo guiado

`/operator/guiado` (boton "Paso a paso" en el panel): muestra un solo paso a la vez en lenguaje llano
(Cargar -> Revisar -> Entregar). La logica vive en `src/perfect_catalog/guided_flow.py` (funcion pura
sobre los mismos conteos del panel). El panel completo no cambio.

## Vista Simple / Completa (idea tomada de Kairo OmegaCreator V3.0)

Boton "Vista: Completa/Simple" en la barra superior (`static/view-mode.js`, preferencia solo en el
navegador, por defecto Completa = comportamiento de siempre). Lo marcado `data-advanced` se oculta en
vista Simple (menu Administracion, franja de administracion del panel, pie tecnico) y "Inicio" lleva a
`/operator/guiado`. Las explicaciones largas van plegadas en "¿Como funciona?".

Ideas de Kairo evaluadas y aun no aplicadas (Kairo solo trae la interfaz; su servidor esta compilado):
revision de calidad de datos antes de generar (codigos repetidos, filas sin codigo, nombres repetidos
con codigos distintos, referencias sin foto), boton "Eliminar referencias sin foto" en bloque,
plantilla de encabezado con `{marca}` `{empresa}` `{total}`, campo WhatsApp para pedidos, salida PDF
para imprimir, interruptor de marca de agua con logo propio por marca, PWA instalable, visibilidad de
funciones configurable por administrador.

## Seleccion manual de fotos (idea de Kairo, migracion 0029)

En `/operator/images`, cada foto "sin asociar o ambigua" tiene un buscador "¿De que producto es esta
foto?": se busca por referencia o nombre y se asigna como foto principal o adicional. Crea un candidato
`operator-selected-v1` + su decision `approved` (append-only, con el actor) en una transaccion
(`src/perfect_catalog/image_manual_selection.py`); despues se copia con "Preparar coincidencias exactas".
**Pendiente: aplicar la 0029 con `ACTUALIZAR-SISTEMA.cmd` (cerrar servidores; antes `RESPALDAR-BASE.cmd`) y
probar en vivo.** El SQL de busqueda/asignacion solo esta probado con un gateway simulado, no contra Postgres.
Sin hacer: "Descartar foto" (no hay candidato al que adjuntar un rechazo) y "Excluir referencias sin foto".

## App de escritorio (Nexo ISA)

`INICIAR-APP.cmd` (o el acceso directo creado con `CREAR-ACCESO-DIRECTO.cmd`) arranca consola + generador
publico en UN proceso (`src/perfect_catalog/desktop_app.py`), pide la contrasena de PostgreSQL UNA vez en una
ventana (no se guarda), entra solo con un boleto de un solo uso (`/operator/app-login?ticket=`, sesion de 12 h) y
abre una ventana de Edge/Chrome en modo app (sin pestanas ni URL, perfil propio en %LOCALAPPDATA%\NexoISA).
Al cerrar la ventana se apagan los servidores. Errores: `logs\desktop-app.log`.
**Verificado**: servidores en hilos + login por boleto sobre TCP real y apagado limpio (script de humo).
**Sin verificar en vivo**: el dialogo de contrasena (Tk) y la ventana de Edge; si Edge cede el control a otra
instancia, la app cae a una ventanita "Apagar" y abre el navegador normal. Los lanzadores clasicos
(INICIAR-REVISOR/TODO) siguen funcionando igual. Las guardas de ACTUALIZAR/LIMPIAR tambien detectan la app.

## Arquitectura en una linea

Operador: `src/perfect_catalog/operator_api.py`. Generador publico: `public_catalog.py`,
`public_generator_api.py`, `public_catalog_links.py`. Importador/revision/publicacion:
`importer.py`, `reviews.py`, `publication.py`. Exportaciones: `catalog_exports.py`,
`catalog_export_job.py`. Migraciones: `db/migrations/`.

## Pendiente (en orden)

1. **Verificacion en vivo sin confirmar**: flujo completo Cargar -> Revisar -> Aprobar -> Entregar
   con una referencia de Excel nunca usada. El bug "Las versiones del plan no coinciden con el
   codigo actual" ya esta corregido (los planes con version obsoleta se ocultan de "Entregar").
2. **Probar los lanzadores nuevos** con doble clic (no se pudo probar el arranque completo porque
   pide la contrasena de Postgres de forma interactiva).
3. **Marca de agua en fotos del generador publico**: pedida, alcance "Generador publico"
   (`public_catalog.py` / `catalog_exports.py`). Sin codigo escrito.
4. **Fusionar `workflow-3-etapas` en `master`** (decision pendiente) y subir los commits locales.
5. No retomar el rediseno de Fase B (fotos inline en la cola de revision) hasta confirmar el
   punto 1.
6. Seguridad: la contrasena de Postgres se pego en un chat anterior; sigue recomendado rotarla.

## Ideas evaluadas y no priorizadas

Respaldo automatico de la base con `pg_dump` programado; partir `operator_api.py` (~3.000 lineas)
por pantallas; pasar la API (puerto 8080, `start_published_catalog.ps1`) por el lanzador comun.
