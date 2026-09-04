BEGIN;

ALTER TABLE perfect_catalog.brand_profile
    ADD COLUMN IF NOT EXISTS company_id uuid;

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_brand_profile_company'
                   AND conrelid='perfect_catalog.brand_profile'::regclass) THEN
        ALTER TABLE perfect_catalog.brand_profile
            ADD CONSTRAINT fk_brand_profile_company
            FOREIGN KEY (company_id) REFERENCES perfect_catalog.company (company_id) ON DELETE RESTRICT;
    END IF;
END
$migration$;

UPDATE perfect_catalog.brand_profile AS bp
SET company_id = COALESCE(
    b.company_id,
    '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
)
FROM perfect_catalog.brand AS b
WHERE b.code = bp.code
  AND bp.company_id IS NULL;

UPDATE perfect_catalog.brand_profile
SET company_id = '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE company_id IS NULL;

ALTER TABLE perfect_catalog.brand_profile
    ALTER COLUMN company_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS ix_brand_profile_company_name
ON perfect_catalog.brand_profile (company_id, display_name, code);

ALTER TABLE perfect_catalog.visual_identity_revision
    ADD COLUMN IF NOT EXISTS company_id uuid;

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_visual_identity_revision_company'
                   AND conrelid='perfect_catalog.visual_identity_revision'::regclass) THEN
        ALTER TABLE perfect_catalog.visual_identity_revision
            ADD CONSTRAINT fk_visual_identity_revision_company
            FOREIGN KEY (company_id) REFERENCES perfect_catalog.company (company_id) ON DELETE RESTRICT;
    END IF;
END
$migration$;

UPDATE perfect_catalog.visual_identity_revision
SET company_id = '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE scope = 'company';

ALTER TABLE perfect_catalog.visual_identity_revision
    DROP CONSTRAINT IF EXISTS ck_visual_identity_revision_target;

ALTER TABLE perfect_catalog.visual_identity_revision
    ADD CONSTRAINT ck_visual_identity_revision_target
        CHECK (
            (scope='company' AND company_id IS NOT NULL AND brand_profile_id IS NULL AND vehicle_make_id IS NULL)
            OR (scope='brand' AND company_id IS NULL AND brand_profile_id IS NOT NULL AND vehicle_make_id IS NULL)
            OR (scope='vehicle_make' AND company_id IS NULL AND brand_profile_id IS NULL AND vehicle_make_id IS NOT NULL)
        );

CREATE INDEX IF NOT EXISTS ix_visual_identity_revision_company_latest
ON perfect_catalog.visual_identity_revision (company_id, created_at DESC)
WHERE scope='company';

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0019_company_visual_identity', :'checksum_0019', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Perfil e identidad corporativa ligados a Company; revisiones company historicas asignadas a PERFECT.'
);

COMMIT;
