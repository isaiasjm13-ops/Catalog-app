# Promoción de cuarentena a dry-run

La recepción y el procesamiento permanecen separados. Subir un archivo sólo crea un objeto
content-addressed y un evento de ingreso; nunca perfila ni importa automáticamente.

## Migración

Ejecutar `ACTUALIZAR-SISTEMA.cmd` como administrador de la base. El actualizador aplica `0008` solamente si falta y crea
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
ejecuciones concurrentes. El bloqueo es de sesión y vive en una conexión autocommit separada: la
transacción SERIALIZABLE de lectura se confirma antes de que otra conexión cree el plan del dry-run,
y el enlace final usa un snapshot nuevo que ya puede validar su FK. Ningún paso aprueba, aplica,
activa o publica productos. Ante un fallo
antes de completar el dry-run se elimina la copia de procesamiento; si el plan ya quedó persistido,
la copia se conserva para no romper la ruta auditada en `import_file`. El original permanece intacto.

## Consola del operador

Después de aplicar `0008`, `INICIAR-REVISOR.cmd` muestra **Promover a dry-run** únicamente en ingresos
Odoo aceptados que aún no tengan promoción. La acción requiere un POST individual, sesión vigente,
Origin local, CSRF exacto, motivo y confirmación. No existe promoción por GET ni selección masiva.
Al completar, el historial muestra el plan enlazado; éste continúa en `awaiting_review`.
Un fallo inesperado devuelve un identificador diagnóstico de 8 caracteres que también aparece en la
consola junto al tipo de excepción y SQLSTATE, pero no muestra ni registra el mensaje crudo potencialmente sensible.
