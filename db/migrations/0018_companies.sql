BEGIN;

CREATE TABLE perfect_catalog.company (
    company_id uuid NOT NULL,
    code text NOT NULL,
    display_name text NOT NULL,
    normalized_name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_company PRIMARY KEY (company_id),
    CONSTRAINT uq_company_code UNIQUE (code),
    CONSTRAINT uq_company_normalized_name UNIQUE (normalized_name),
    CONSTRAINT ck_company_code CHECK (code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'),
    CONSTRAINT ck_company_name CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_company_normalized_name CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_company_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

INSERT INTO perfect_catalog.company (
    company_id, code, display_name, normalized_name, metadata
) VALUES
    ('2ec779ba-2355-5151-babd-704cfa8f3ef0', 'PERFECT', 'Perfect Company', 'PERFECT COMPANY', '{"seed":"specification-v12"}'),
    ('695244ca-0c58-576c-a12e-56a4401a53f2', 'KMC', 'KMC - King Motors Company', 'KMC KING MOTORS COMPANY', '{"seed":"specification-v12"}'),
    ('ee7c7e0c-398f-5e35-9d79-c97d761f8672', 'NATSUKI', 'Natsuki', 'NATSUKI', '{"seed":"specification-v12"}'),
    ('25f16c9a-0064-5a6d-9e36-61f8db190a7c', 'MASAKI', 'Masaki', 'MASAKI', '{"seed":"specification-v12"}'),
    ('84df94ab-7ad5-5f02-8b9f-2f5ef4701f6b', 'PDM', 'PDM', 'PDM', '{"seed":"specification-v12","brand_policy":"oem_only"}');

ALTER TABLE perfect_catalog.brand ADD COLUMN company_id uuid;

ALTER TABLE perfect_catalog.brand
    ADD CONSTRAINT fk_brand_company FOREIGN KEY (company_id)
    REFERENCES perfect_catalog.company (company_id) ON DELETE RESTRICT;

UPDATE perfect_catalog.brand
SET company_id = CASE code
    WHEN 'EXACTCARS' THEN '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
    WHEN 'NATSUKI' THEN 'ee7c7e0c-398f-5e35-9d79-c97d761f8672'::uuid
END
WHERE code IN ('EXACTCARS', 'NATSUKI');

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM perfect_catalog.brand WHERE company_id IS NULL) THEN
        RAISE EXCEPTION 'Hay marcas sin mapping Company; 0018 se cancela sin cambios.';
    END IF;
END $$;

ALTER TABLE perfect_catalog.brand ALTER COLUMN company_id SET NOT NULL;

CREATE INDEX ix_brand_company_active_name
ON perfect_catalog.brand (company_id, is_active, normalized_name);

REVOKE ALL ON perfect_catalog.company FROM PUBLIC;
GRANT SELECT ON perfect_catalog.company TO perfect_catalog_app, perfect_catalog_readonly;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0018_companies', :'checksum_0018', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Companies iniciales; EXACTCARS->PERFECT y NATSUKI->NATSUKI aprobados.'
);

COMMIT;
