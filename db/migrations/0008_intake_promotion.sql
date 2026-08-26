BEGIN;

-- Estas claves pueden existir si una preparación anterior llegó hasta este punto.
-- La comprobación permite reanudar sin eliminar ni recrear datos o restricciones.
DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_intake_submission_asset'
          AND conrelid = 'perfect_catalog.intake_submission'::regclass
    ) THEN
        ALTER TABLE perfect_catalog.intake_submission
            ADD CONSTRAINT uq_intake_submission_asset
            UNIQUE (intake_submission_id, intake_asset_id);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_intake_asset_identity_sha'
          AND conrelid = 'perfect_catalog.intake_asset'::regclass
    ) THEN
        ALTER TABLE perfect_catalog.intake_asset
            ADD CONSTRAINT uq_intake_asset_identity_sha
            UNIQUE (intake_asset_id, sha256);
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'uq_import_plan_batch'
          AND conrelid = 'perfect_catalog.import_plan'::regclass
    ) THEN
        ALTER TABLE perfect_catalog.import_plan
            ADD CONSTRAINT uq_import_plan_batch
            UNIQUE (import_plan_id, import_batch_id);
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS perfect_catalog.intake_promotion (
    intake_promotion_id uuid NOT NULL,
    intake_submission_id uuid NOT NULL,
    intake_asset_id uuid NOT NULL,
    import_batch_id uuid NOT NULL,
    import_plan_id uuid NOT NULL,
    source_sha256 text NOT NULL,
    processing_relpath text NOT NULL,
    profile_report jsonb NOT NULL,
    column_suggestions jsonb NOT NULL,
    promoted_by text NOT NULL,
    reason text NOT NULL,
    promoted_at timestamp with time zone NOT NULL,
    CONSTRAINT pk_intake_promotion PRIMARY KEY (intake_promotion_id),
    CONSTRAINT uq_intake_promotion_submission UNIQUE (intake_submission_id),
    CONSTRAINT uq_intake_promotion_plan UNIQUE (import_plan_id),
    CONSTRAINT fk_intake_promotion_submission_asset
        FOREIGN KEY (intake_submission_id, intake_asset_id)
        REFERENCES perfect_catalog.intake_submission (intake_submission_id, intake_asset_id)
        ON DELETE RESTRICT,
    CONSTRAINT fk_intake_promotion_asset_sha
        FOREIGN KEY (intake_asset_id, source_sha256)
        REFERENCES perfect_catalog.intake_asset (intake_asset_id, sha256) ON DELETE RESTRICT,
    CONSTRAINT fk_intake_promotion_plan_batch
        FOREIGN KEY (import_plan_id, import_batch_id)
        REFERENCES perfect_catalog.import_plan (import_plan_id, import_batch_id) ON DELETE RESTRICT,
    CONSTRAINT ck_intake_promotion_sha256 CHECK (source_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_intake_promotion_path CHECK (
        processing_relpath ~ '^processing/[0-9a-f-]{36}/[^/\\]{1,240}$'
    ),
    CONSTRAINT ck_intake_promotion_profile CHECK (jsonb_typeof(profile_report) = 'object'),
    CONSTRAINT ck_intake_promotion_columns CHECK (jsonb_typeof(column_suggestions) = 'object'),
    CONSTRAINT ck_intake_promotion_actor CHECK (
        btrim(promoted_by) <> '' AND char_length(promoted_by) <= 120
    ),
    CONSTRAINT ck_intake_promotion_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

DO $migration$
DECLARE
    missing_constraint text;
BEGIN
    SELECT expected.name INTO missing_constraint
    FROM (VALUES
        ('pk_intake_promotion'),
        ('uq_intake_promotion_submission'),
        ('uq_intake_promotion_plan'),
        ('fk_intake_promotion_submission_asset'),
        ('fk_intake_promotion_asset_sha'),
        ('fk_intake_promotion_plan_batch'),
        ('ck_intake_promotion_sha256'),
        ('ck_intake_promotion_path'),
        ('ck_intake_promotion_profile'),
        ('ck_intake_promotion_columns'),
        ('ck_intake_promotion_actor'),
        ('ck_intake_promotion_reason')
    ) AS expected(name)
    WHERE NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = expected.name
          AND conrelid = 'perfect_catalog.intake_promotion'::regclass
    )
    LIMIT 1;
    IF missing_constraint IS NOT NULL THEN
        RAISE EXCEPTION 'La tabla intake_promotion está incompleta; falta %', missing_constraint;
    END IF;
END
$migration$;

CREATE INDEX IF NOT EXISTS ix_intake_promotion_promoted
    ON perfect_catalog.intake_promotion (promoted_at DESC, intake_promotion_id DESC);

DO $migration$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_intake_promotion_append_only'
          AND tgrelid = 'perfect_catalog.intake_promotion'::regclass
          AND NOT tgisinternal
    ) THEN
        CREATE TRIGGER trg_intake_promotion_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.intake_promotion
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

REVOKE ALL ON perfect_catalog.intake_promotion
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;

GRANT SELECT, INSERT ON perfect_catalog.intake_promotion TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.intake_promotion TO perfect_catalog_readonly;

COMMIT;
