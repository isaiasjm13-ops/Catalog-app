BEGIN;

ALTER TABLE perfect_catalog.brand_profile
    ADD COLUMN company_id uuid;

ALTER TABLE perfect_catalog.brand_profile
    ADD CONSTRAINT fk_brand_profile_company
        FOREIGN KEY (company_id)
        REFERENCES perfect_catalog.company (company_id)
        ON DELETE RESTRICT;

UPDATE perfect_catalog.brand_profile AS bp
SET company_id = b.company_id
FROM perfect_catalog.brand AS b
WHERE b.brand_profile_id = bp.brand_profile_id;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM perfect_catalog.brand_profile WHERE company_id IS NULL) THEN
        RAISE EXCEPTION 'Hay perfiles de marca sin Company; 0019 se cancela sin cambios.';
    END IF;
END $$;

ALTER TABLE perfect_catalog.brand_profile
    ALTER COLUMN company_id SET NOT NULL;

CREATE INDEX ix_brand_profile_company_name
ON perfect_catalog.brand_profile (company_id, display_name, code);

ALTER TABLE perfect_catalog.visual_identity_revision
    ADD COLUMN company_id uuid;

ALTER TABLE perfect_catalog.visual_identity_revision
    ADD CONSTRAINT fk_visual_identity_revision_company
        FOREIGN KEY (company_id)
        REFERENCES perfect_catalog.company (company_id)
        ON DELETE RESTRICT;

UPDATE perfect_catalog.visual_identity_revision
SET company_id = '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE scope = 'company';

ALTER TABLE perfect_catalog.visual_identity_revision
    DROP CONSTRAINT ck_visual_identity_revision_target,
    ADD CONSTRAINT ck_visual_identity_revision_target
        CHECK (
            (scope='company' AND company_id IS NOT NULL AND brand_profile_id IS NULL AND vehicle_make_id IS NULL)
            OR (scope='brand' AND company_id IS NULL AND brand_profile_id IS NOT NULL AND vehicle_make_id IS NULL)
            OR (scope='vehicle_make' AND company_id IS NULL AND brand_profile_id IS NULL AND vehicle_make_id IS NOT NULL)
        );

CREATE INDEX ix_visual_identity_revision_company_latest
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
