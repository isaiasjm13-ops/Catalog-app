BEGIN;

ALTER TABLE perfect_catalog.intake_submission
    ADD COLUMN company_id uuid;

ALTER TABLE perfect_catalog.intake_submission
    ADD CONSTRAINT fk_intake_submission_company
        FOREIGN KEY (company_id) REFERENCES perfect_catalog.company (company_id)
        ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.import_plan
    ADD COLUMN company_id uuid;

ALTER TABLE perfect_catalog.import_plan
    ADD CONSTRAINT fk_import_plan_company
        FOREIGN KEY (company_id) REFERENCES perfect_catalog.company (company_id)
        ON DELETE RESTRICT;

UPDATE perfect_catalog.import_plan AS p
SET company_id = bp.company_id
FROM perfect_catalog.brand_profile AS bp
WHERE bp.brand_profile_id=p.brand_profile_id;

-- intake_submission es append-only: el historial no se reescribe ni siquiera cuando
-- existe una promoción relacionada. Los ingresos anteriores quedan con company_id
-- nulo, fuera de las vistas por Company, hasta una reasignación auditada separada.

CREATE INDEX ix_intake_submission_company_submitted
ON perfect_catalog.intake_submission (company_id, submitted_at DESC, intake_submission_id DESC);

CREATE INDEX ix_import_plan_company_generated
ON perfect_catalog.import_plan (company_id, generated_at DESC, import_plan_id DESC);

CREATE FUNCTION perfect_catalog.require_company_context()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.company_id IS NULL THEN
        RAISE EXCEPTION 'company_id es obligatorio para nuevos registros de %', TG_TABLE_NAME;
    END IF;
    RETURN NEW;
END
$$;

REVOKE ALL ON FUNCTION perfect_catalog.require_company_context() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION perfect_catalog.require_company_context()
TO perfect_catalog_app;

CREATE TRIGGER trg_intake_submission_company_required
BEFORE INSERT ON perfect_catalog.intake_submission
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.require_company_context();

CREATE TRIGGER trg_import_plan_company_required
BEFORE INSERT ON perfect_catalog.import_plan
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.require_company_context();

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0020_company_intake_context', :'checksum_0020', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Company persistida desde ingreso hasta plan; historicos se asignan solo con evidencia relacional.'
);

COMMIT;
