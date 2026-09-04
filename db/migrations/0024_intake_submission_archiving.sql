BEGIN;

-- intake_submission es completamente append-only (0007): ninguna columna admite UPDATE.
-- Para poder ocultar ingresos viejos de la lista activa sin tocar esa evidencia ni debilitar
-- su guardia, el estado "archivado" se registra como eventos separados (mismo patron que
-- image_product_decision): el ultimo evento por ingreso determina su estado vigente.
CREATE TABLE IF NOT EXISTS perfect_catalog.intake_submission_archive_event (
    intake_submission_archive_event_id uuid PRIMARY KEY,
    intake_submission_id uuid NOT NULL REFERENCES perfect_catalog.intake_submission(intake_submission_id) ON DELETE RESTRICT,
    archived boolean NOT NULL,
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_intake_submission_archive_event_submission
    ON perfect_catalog.intake_submission_archive_event (intake_submission_id, created_at DESC);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_intake_submission_archive_event_append_only'
                   AND tgrelid='perfect_catalog.intake_submission_archive_event'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_intake_submission_archive_event_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.intake_submission_archive_event
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

REVOKE ALL ON perfect_catalog.intake_submission_archive_event FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.intake_submission_archive_event TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.intake_submission_archive_event TO perfect_catalog_readonly;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0024_intake_submission_archiving', :'checksum_0024', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Archivado auditado y reversible de ingresos viejos sin tocar su evidencia append-only.'
);

COMMIT;
