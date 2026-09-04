BEGIN;

-- 0021/0022 fijaron el contexto de marca desde brand.brand_profile_id, pero ninguna
-- migracion ni pantalla lo completa para Companies nuevas (KMC/A1, PDM): solo NATSUKI
-- quedo vinculada por un UPDATE puntual en 0014. Sin este vinculo, un dry-run nuevo
-- para cualquier otra Brand queda con brand_profile_id nulo y jamas puede aprobarse
-- (approve_and_apply_plan y publication._resolve_plan_brand lo exigen no nulo).
CREATE TABLE IF NOT EXISTS perfect_catalog.brand_profile_link_event (
    brand_profile_link_event_id uuid PRIMARY KEY,
    brand_id uuid NOT NULL REFERENCES perfect_catalog.brand(brand_id) ON DELETE RESTRICT,
    previous_brand_profile_id uuid REFERENCES perfect_catalog.brand_profile(brand_profile_id) ON DELETE RESTRICT,
    new_brand_profile_id uuid NOT NULL REFERENCES perfect_catalog.brand_profile(brand_profile_id) ON DELETE RESTRICT,
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    reason text NOT NULL CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT ck_brand_profile_link_event_changes CHECK (
        previous_brand_profile_id IS DISTINCT FROM new_brand_profile_id
    )
);

CREATE INDEX IF NOT EXISTS ix_brand_profile_link_event_brand
    ON perfect_catalog.brand_profile_link_event (brand_id, created_at DESC);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_brand_profile_link_event_append_only'
                   AND tgrelid='perfect_catalog.brand_profile_link_event'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_brand_profile_link_event_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.brand_profile_link_event
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

REVOKE ALL ON perfect_catalog.brand_profile_link_event FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.brand_profile_link_event TO perfect_catalog_app;
GRANT UPDATE (brand_profile_id, updated_at) ON perfect_catalog.brand TO perfect_catalog_app;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0023_brand_profile_linking', :'checksum_0023', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Vinculo auditado Brand -> Brand Profile para completar el contexto que exige el dry-run multiempresa.'
);

COMMIT;
