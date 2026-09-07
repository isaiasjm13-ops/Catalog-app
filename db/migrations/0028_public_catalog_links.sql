BEGIN;

-- Generador público de catálogos (self-service externo, sin login): dos tablas nuevas,
-- sin FK hacia product_reference/company/brand, para que nada de lo que suba un externo
-- pueda chocar con el catálogo real. public_catalog_link es el enlace único que se le
-- reparte a cada externo; siguiendo el patrón append-only del resto del esquema (ver
-- intake_submission_archive_event en 0024), la revocación es un evento aparte, no un
-- UPDATE sobre la fila del link — un link revocado lo es para siempre, y para reactivar
-- el acceso se crea un link nuevo. public_catalog_generation es la bitácora: qué link
-- (y qué nombre declaró la persona) generó cada catálogo.

CREATE TABLE IF NOT EXISTS perfect_catalog.public_catalog_link (
    public_catalog_link_id uuid PRIMARY KEY,
    token text NOT NULL UNIQUE CHECK (btrim(token) <> ''),
    label text NOT NULL CHECK (btrim(label) <> ''),
    created_by_actor text NOT NULL CHECK (btrim(created_by_actor) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_public_catalog_link_append_only'
                   AND tgrelid='perfect_catalog.public_catalog_link'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_public_catalog_link_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.public_catalog_link
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS perfect_catalog.public_catalog_link_revocation_event (
    public_catalog_link_revocation_event_id uuid PRIMARY KEY,
    public_catalog_link_id uuid NOT NULL REFERENCES perfect_catalog.public_catalog_link(public_catalog_link_id) ON DELETE RESTRICT,
    actor text NOT NULL CHECK (btrim(actor) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_public_catalog_link_revocation_event_link
    ON perfect_catalog.public_catalog_link_revocation_event (public_catalog_link_id);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_public_catalog_link_revocation_event_append_only'
                   AND tgrelid='perfect_catalog.public_catalog_link_revocation_event'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_public_catalog_link_revocation_event_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.public_catalog_link_revocation_event
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

CREATE TABLE IF NOT EXISTS perfect_catalog.public_catalog_generation (
    public_catalog_generation_id uuid PRIMARY KEY,
    public_catalog_link_id uuid NOT NULL REFERENCES perfect_catalog.public_catalog_link(public_catalog_link_id) ON DELETE RESTRICT,
    declared_name text NOT NULL CHECK (btrim(declared_name) <> ''),
    product_count integer NOT NULL CHECK (product_count >= 0),
    matched_image_count integer NOT NULL CHECK (matched_image_count >= 0),
    unmatched_image_count integer NOT NULL CHECK (unmatched_image_count >= 0),
    ambiguous_image_count integer NOT NULL CHECK (ambiguous_image_count >= 0),
    excel_sha256 text NOT NULL CHECK (excel_sha256 ~ '^[0-9a-f]{64}$'),
    client_ip text,
    generated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_public_catalog_generation_link
    ON perfect_catalog.public_catalog_generation (public_catalog_link_id, generated_at DESC);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_public_catalog_generation_append_only'
                   AND tgrelid='perfect_catalog.public_catalog_generation'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_public_catalog_generation_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.public_catalog_generation
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

REVOKE ALL ON perfect_catalog.public_catalog_link FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.public_catalog_link TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.public_catalog_link TO perfect_catalog_readonly;

REVOKE ALL ON perfect_catalog.public_catalog_link_revocation_event FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.public_catalog_link_revocation_event TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.public_catalog_link_revocation_event TO perfect_catalog_readonly;

REVOKE ALL ON perfect_catalog.public_catalog_generation FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.public_catalog_generation TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.public_catalog_generation TO perfect_catalog_readonly;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0028_public_catalog_links', :'checksum_0028', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Links de acceso y bitácora del generador público de catálogos (self-service externo, sin login, sin tocar product_reference/company/brand).'
);

COMMIT;
