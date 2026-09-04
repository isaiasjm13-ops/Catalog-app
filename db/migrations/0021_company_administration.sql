BEGIN;

CREATE TABLE IF NOT EXISTS perfect_catalog.company_admin_event (
    company_admin_event_id uuid PRIMARY KEY,
    company_id uuid NOT NULL REFERENCES perfect_catalog.company(company_id) ON DELETE RESTRICT,
    action text NOT NULL CHECK (action IN ('created','deactivated','reactivated')),
    code_snapshot text NOT NULL,
    display_name_snapshot text NOT NULL,
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_company_admin_event_append_only'
                   AND tgrelid='perfect_catalog.company_admin_event'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_company_admin_event_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.company_admin_event
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

INSERT INTO perfect_catalog.company (company_id, code, display_name, normalized_name, metadata)
VALUES
    ('2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid, 'PERFECT', 'Perfect Trading', 'PERFECT TRADING', '{"seed":"migration-0021"}'::jsonb),
    ('695244ca-0c58-576c-a12e-56a4401a53f2'::uuid, 'KMC', 'KMC - King Motors Company', 'KMC KING MOTORS COMPANY', '{"seed":"migration-0021"}'::jsonb),
    ('84df94ab-7ad5-5f02-8b9f-2f5ef4701f6b'::uuid, 'PDM', 'PDM', 'PDM', '{"seed":"migration-0021","brand_policy":"oem_only"}'::jsonb)
ON CONFLICT (code) DO UPDATE
SET display_name=EXCLUDED.display_name,
    normalized_name=EXCLUDED.normalized_name,
    is_active=true,
    updated_at=CURRENT_TIMESTAMP;

-- Natsuki y Masaki son marcas de producto de Perfect, no Companies.
UPDATE perfect_catalog.brand
SET company_id='2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE code IN ('NATSUKI','MASAKI');

INSERT INTO perfect_catalog.brand (brand_id, code, name, normalized_name, metadata, company_id)
VALUES
    ('e9f8c1a8-ef34-5c2a-a8d0-7b2d45a1f001'::uuid, 'PERFECT', 'Perfect', 'PERFECT', '{"seed":"migration-0021"}'::jsonb, '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid),
    ('9ed94760-1423-5e1f-a026-48e744de2ccd'::uuid, 'NATSUKI', 'Natsuki', 'NATSUKI', '{"seed":"migration-0021"}'::jsonb, '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid),
    ('2b1a6f92-3bd8-5c7d-8f10-7d5d6a2b1002'::uuid, 'MASAKI', 'Masaki', 'MASAKI', '{"seed":"migration-0021"}'::jsonb, '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid),
    ('4c2d7e83-4ce9-5d8e-9011-8e6e7b3c2003'::uuid, 'EXACTCARS', 'Exact Cars', 'EXACT CARS', '{"seed":"migration-0021"}'::jsonb, '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid)
ON CONFLICT (code) DO UPDATE
SET name=EXCLUDED.name,
    normalized_name=EXCLUDED.normalized_name,
    company_id='2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid;

INSERT INTO perfect_catalog.brand (brand_id, code, name, normalized_name, metadata, company_id)
VALUES ('5d3e8f94-5dfa-5e9f-a122-9f7f8c4d3004'::uuid, 'A1', 'A1', 'A1', '{"seed":"migration-0021"}'::jsonb,
        '695244ca-0c58-576c-a12e-56a4401a53f2'::uuid)
ON CONFLICT (code) DO UPDATE
SET name=EXCLUDED.name,
    normalized_name=EXCLUDED.normalized_name,
    company_id='695244ca-0c58-576c-a12e-56a4401a53f2'::uuid;

UPDATE perfect_catalog.brand
SET company_id='2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE code IN ('PERFECT','EXACTCARS');

UPDATE perfect_catalog.brand_profile
SET company_id='2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid
WHERE code IN ('NATSUKI','MASAKI');

UPDATE perfect_catalog.import_plan AS p
SET company_id=bp.company_id
FROM perfect_catalog.brand_profile AS bp
WHERE p.brand_profile_id=bp.brand_profile_id AND p.company_id IS DISTINCT FROM bp.company_id;

DO $migration$
DECLARE
    legacy record;
    fk record;
    has_references boolean;
    referenced boolean;
BEGIN
    FOR legacy IN SELECT company_id, code, display_name FROM perfect_catalog.company WHERE code IN ('NATSUKI','MASAKI') LOOP
        has_references := false;
        FOR fk IN
            SELECT c.conrelid::regclass AS table_name, a.attname AS column_name
            FROM pg_constraint AS c
            JOIN LATERAL unnest(c.conkey) WITH ORDINALITY AS keys(attnum, position) ON true
            JOIN pg_attribute AS a ON a.attrelid=c.conrelid AND a.attnum=keys.attnum
            WHERE c.contype='f' AND c.confrelid='perfect_catalog.company'::regclass
              AND array_length(c.conkey, 1)=1 AND array_length(c.confkey, 1)=1
        LOOP
            EXECUTE format('SELECT EXISTS (SELECT 1 FROM %s WHERE %I = $1)', fk.table_name, fk.column_name)
                INTO referenced USING legacy.company_id;
            has_references := has_references OR referenced;
        END LOOP;
        IF has_references THEN
            INSERT INTO perfect_catalog.company_admin_event
                (company_admin_event_id, company_id, action, code_snapshot, display_name_snapshot, actor, reason)
            SELECT gen_random_uuid(), legacy.company_id, 'deactivated', legacy.code, legacy.display_name,
                   current_user, 'Company legacy conservada por referencias historicas'
            WHERE EXISTS (SELECT 1 FROM perfect_catalog.company WHERE company_id=legacy.company_id AND is_active);
            UPDATE perfect_catalog.company SET is_active=false, updated_at=CURRENT_TIMESTAMP
            WHERE company_id=legacy.company_id AND is_active;
        ELSE
            DELETE FROM perfect_catalog.company WHERE company_id=legacy.company_id;
        END IF;
    END LOOP;
END
$migration$;

REVOKE ALL ON perfect_catalog.company_admin_event FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.company_admin_event TO perfect_catalog_app;
GRANT INSERT ON perfect_catalog.company TO perfect_catalog_app;
GRANT UPDATE (is_active, updated_at) ON perfect_catalog.company TO perfect_catalog_app;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0021_company_administration', :'checksum_0021', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Natsuki/Masaki reclasificadas como marcas de Perfect; alta y desactivacion auditada de Companies.'
);

COMMIT;
