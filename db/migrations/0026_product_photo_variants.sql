BEGIN;

ALTER TABLE perfect_catalog.image_product_candidate
    ADD COLUMN IF NOT EXISTS variant_index integer NULL;

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='ck_image_product_candidate_variant_index'
                   AND conrelid='perfect_catalog.image_product_candidate'::regclass) THEN
        ALTER TABLE perfect_catalog.image_product_candidate
            ADD CONSTRAINT ck_image_product_candidate_variant_index CHECK (variant_index IS NULL OR variant_index >= 2);
    END IF;
END
$migration$;

ALTER TABLE perfect_catalog.image_product_candidate
    DROP CONSTRAINT IF EXISTS ck_image_product_candidate_algorithm;

ALTER TABLE perfect_catalog.image_product_candidate
    ADD CONSTRAINT ck_image_product_candidate_algorithm
    CHECK (algorithm IN ('exact-approved-reference-v1', 'exact-approved-reference-v2'));

CREATE TABLE IF NOT EXISTS perfect_catalog.approved_image_variant (
    approved_image_variant_id uuid NOT NULL,
    image_product_decision_id uuid NOT NULL,
    image_product_candidate_id uuid NOT NULL,
    image_archive_entry_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    product_target_id uuid GENERATED ALWAYS AS (COALESCE(product_variant_id, product_template_id)) STORED,
    variant_index integer NOT NULL,
    content_sha256 char(64) NOT NULL,
    media_type text NOT NULL,
    byte_size bigint NOT NULL,
    storage_relpath text NOT NULL,
    original_filename text NOT NULL,
    materialized_by text NOT NULL,
    reason text NOT NULL,
    materialized_at timestamptz NOT NULL,
    CONSTRAINT pk_approved_image_variant PRIMARY KEY (approved_image_variant_id),
    CONSTRAINT uq_approved_image_variant_decision UNIQUE (image_product_decision_id),
    CONSTRAINT uq_approved_image_variant_target_index UNIQUE (product_target_id, variant_index),
    CONSTRAINT fk_approved_image_variant_decision FOREIGN KEY (image_product_decision_id)
        REFERENCES perfect_catalog.image_product_decision (image_product_decision_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_variant_candidate FOREIGN KEY (image_product_candidate_id)
        REFERENCES perfect_catalog.image_product_candidate (image_product_candidate_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_variant_entry FOREIGN KEY (image_archive_entry_id)
        REFERENCES perfect_catalog.image_archive_entry (image_archive_entry_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_variant_template FOREIGN KEY (product_template_id)
        REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_variant_variant FOREIGN KEY (product_variant_id)
        REFERENCES perfect_catalog.product_variant (product_variant_id) ON DELETE RESTRICT,
    CONSTRAINT ck_approved_image_variant_index CHECK (variant_index >= 2),
    CONSTRAINT ck_approved_image_variant_sha CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_approved_image_variant_media CHECK (btrim(media_type) <> ''),
    CONSTRAINT ck_approved_image_variant_size CHECK (byte_size >= 0),
    CONSTRAINT ck_approved_image_variant_path CHECK (storage_relpath ~ '^objects/[0-9a-f]{2}/[0-9a-f]{64}\.[a-z0-9]{1,12}$'),
    CONSTRAINT ck_approved_image_variant_name CHECK (btrim(original_filename) <> ''),
    CONSTRAINT ck_approved_image_variant_actor CHECK (btrim(materialized_by) <> '' AND char_length(materialized_by) <= 120),
    CONSTRAINT ck_approved_image_variant_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

CREATE INDEX IF NOT EXISTS ix_approved_image_variant_product
ON perfect_catalog.approved_image_variant (product_template_id, product_variant_id);

CREATE INDEX IF NOT EXISTS ix_approved_image_variant_target
ON perfect_catalog.approved_image_variant (product_target_id, variant_index);

DO $migration$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='trg_approved_image_variant_append_only'
                   AND tgrelid='perfect_catalog.approved_image_variant'::regclass AND NOT tgisinternal) THEN
        CREATE TRIGGER trg_approved_image_variant_append_only
        BEFORE UPDATE OR DELETE ON perfect_catalog.approved_image_variant
        FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
    END IF;
END
$migration$;

REVOKE ALL ON perfect_catalog.approved_image_variant
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;
GRANT SELECT, INSERT ON perfect_catalog.approved_image_variant TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.approved_image_variant TO perfect_catalog_readonly;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0026_product_photo_variants', :'checksum_0026', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Fotos variantes por producto (sufijo -2, -3...): tabla nueva approved_image_variant, sin tocar la foto principal.'
);

COMMIT;
