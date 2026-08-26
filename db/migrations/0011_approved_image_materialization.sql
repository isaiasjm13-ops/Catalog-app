BEGIN;

CREATE TABLE perfect_catalog.approved_image_materialization (
    approved_image_materialization_id uuid NOT NULL,
    image_product_decision_id uuid NOT NULL,
    image_product_candidate_id uuid NOT NULL,
    image_archive_entry_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    product_target_id uuid GENERATED ALWAYS AS (COALESCE(product_variant_id, product_template_id)) STORED,
    content_sha256 char(64) NOT NULL,
    media_type text NOT NULL,
    byte_size bigint NOT NULL,
    storage_relpath text NOT NULL,
    original_filename text NOT NULL,
    materialized_by text NOT NULL,
    reason text NOT NULL,
    materialized_at timestamptz NOT NULL,
    CONSTRAINT pk_approved_image_materialization PRIMARY KEY (approved_image_materialization_id),
    CONSTRAINT uq_approved_image_materialization_decision UNIQUE (image_product_decision_id),
    CONSTRAINT uq_approved_image_materialization_target UNIQUE (product_target_id),
    CONSTRAINT fk_approved_image_materialization_decision FOREIGN KEY (image_product_decision_id)
        REFERENCES perfect_catalog.image_product_decision (image_product_decision_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_materialization_candidate FOREIGN KEY (image_product_candidate_id)
        REFERENCES perfect_catalog.image_product_candidate (image_product_candidate_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_materialization_entry FOREIGN KEY (image_archive_entry_id)
        REFERENCES perfect_catalog.image_archive_entry (image_archive_entry_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_materialization_template FOREIGN KEY (product_template_id)
        REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    CONSTRAINT fk_approved_image_materialization_variant FOREIGN KEY (product_variant_id)
        REFERENCES perfect_catalog.product_variant (product_variant_id) ON DELETE RESTRICT,
    CONSTRAINT ck_approved_image_materialization_sha CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_approved_image_materialization_media CHECK (btrim(media_type) <> ''),
    CONSTRAINT ck_approved_image_materialization_size CHECK (byte_size >= 0),
    CONSTRAINT ck_approved_image_materialization_path CHECK (storage_relpath ~ '^objects/[0-9a-f]{2}/[0-9a-f]{64}\.[a-z0-9]{1,12}$'),
    CONSTRAINT ck_approved_image_materialization_name CHECK (btrim(original_filename) <> ''),
    CONSTRAINT ck_approved_image_materialization_actor CHECK (btrim(materialized_by) <> '' AND char_length(materialized_by) <= 120),
    CONSTRAINT ck_approved_image_materialization_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

CREATE INDEX ix_approved_image_materialization_product
ON perfect_catalog.approved_image_materialization (product_template_id, product_variant_id);

CREATE TRIGGER trg_approved_image_materialization_append_only
BEFORE UPDATE OR DELETE ON perfect_catalog.approved_image_materialization
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

REVOKE ALL ON perfect_catalog.approved_image_materialization
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;
GRANT SELECT, INSERT ON perfect_catalog.approved_image_materialization TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.approved_image_materialization TO perfect_catalog_readonly;

COMMIT;
