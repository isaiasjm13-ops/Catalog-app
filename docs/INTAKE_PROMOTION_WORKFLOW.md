# Promoción de cuarentena a dry-run

La recepción y el procesamiento permanecen separados. Subir un archivo sólo crea un objeto
content-addressed y un evento de ingreso; nunca perfila ni importa automáticamente.

## Migración

Ejecutar `MIGRAR-PROMOCIONES.cmd` como administrador de la base. La migración `0008` crea
`intake_promotion`, una evidencia append-only que enlaza exactamente submission, asset/SHA-256,
batch y plan. El rol de aplicación sólo obtiene `SELECT` e `INSERT`.

## Operación explícita

```powershell
.\.venv\Scripts\perfect-catalog.exe promote-intake <SUBMISSION_UUID> `
  --actor <USUARIO> `
  --reason "Exportación completa autorizada para perfilado" `
  --prompt-password
```

La operación sólo admite `odoo_data` con estado `quarantined`. Antes de procesar:

1. confina la ruta a `data/intake`;
2. compara tamaño y SHA-256 con PostgreSQL;
3. crea una copia aislada en `data/intake/processing/<promotion-id>/`;
4. genera perfil y sugerencias de aliases sin modificar datos;
5. ejecuta el dry-run vigente, que termina en `awaiting_review`;
6. registra el vínculo inmutable con el plan generado.

La promoción repetida devuelve `already_promoted`; un bloqueo PostgreSQL por submission evita dos
ejecuciones concurrentes. Ningún paso aprueba, aplica, activa o publica productos. Ante un fallo
antes de completar el dry-run se elimina la copia de procesamiento; si el plan ya quedó persistido,
la copia se conserva para no romper la ruta auditada en `import_file`. El original permanece intacto.

## Consola del operador

Después de aplicar `0008`, `INICIAR-REVISOR.cmd` muestra **Promover a dry-run** únicamente en ingresos
Odoo aceptados que aún no tengan promoción. La acción requiere un POST individual, sesión vigente,
Origin local, CSRF exacto, motivo y confirmación. No existe promoción por GET ni selección masiva.
Al completar, el historial muestra el plan enlazado; éste continúa en `awaiting_review`.
