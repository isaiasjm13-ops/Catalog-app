BEGIN;

CREATE TABLE perfect_catalog.image_product_candidate (
    image_product_candidate_id uuid NOT NULL,
    image_archive_entry_id uuid NOT NULL,
    product_reference_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    algorithm text NOT NULL,
    confidence numeric(5,4) NOT NULL,
    evidence_sha256 char(64) NOT NULL,
    generated_by text NOT NULL,
    reason text NOT NULL,
    generated_at timestamptz NOT NULL,
    CONSTRAINT pk_image_product_candidate PRIMARY KEY (image_product_candidate_id),
    CONSTRAINT uq_image_product_candidate_pair UNIQUE (image_archive_entry_id, product_reference_id),
    CONSTRAINT fk_image_product_candidate_entry FOREIGN KEY (image_archive_entry_id)
        REFERENCES perfect_catalog.image_archive_entry (image_archive_entry_id) ON DELETE RESTRICT,
    CONSTRAINT fk_image_product_candidate_reference FOREIGN KEY (product_reference_id)
        REFERENCES perfect_catalog.product_reference (product_reference_id) ON DELETE RESTRICT,
    CONSTRAINT fk_image_product_candidate_template FOREIGN KEY (product_template_id)
        REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    CONSTRAINT fk_image_product_candidate_variant FOREIGN KEY (product_variant_id)
        REFERENCES perfect_catalog.product_variant (product_variant_id) ON DELETE RESTRICT,
    CONSTRAINT ck_image_product_candidate_algorithm CHECK (algorithm = 'exact-approved-reference-v1'),
    CONSTRAINT ck_image_product_candidate_confidence CHECK (confidence = 1.0000),
    CONSTRAINT ck_image_product_candidate_sha CHECK (evidence_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_image_product_candidate_actor CHECK (btrim(generated_by) <> '' AND char_length(generated_by) <= 120),
    CONSTRAINT ck_image_product_candidate_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

CREATE TABLE perfect_catalog.image_product_decision (
    image_product_decision_id uuid NOT NULL,
    image_product_candidate_id uuid NOT NULL,
    decision text NOT NULL,
    candidate_evidence_sha256 char(64) NOT NULL,
    decided_by text NOT NULL,
    reason text NOT NULL,
    decided_at timestamptz NOT NULL,
    CONSTRAINT pk_image_product_decision PRIMARY KEY (image_product_decision_id),
    CONSTRAINT uq_image_product_decision_candidate UNIQUE (image_product_candidate_id),
    CONSTRAINT fk_image_product_decision_candidate FOREIGN KEY (image_product_candidate_id)
        REFERENCES perfect_catalog.image_product_candidate (image_product_candidate_id) ON DELETE RESTRICT,
    CONSTRAINT ck_image_product_decision_value CHECK (decision IN ('approved', 'rejected')),
    CONSTRAINT ck_image_product_decision_sha CHECK (candidate_evidence_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_image_product_decision_actor CHECK (btrim(decided_by) <> '' AND char_length(decided_by) <= 120),
    CONSTRAINT ck_image_product_decision_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

CREATE INDEX ix_image_product_candidate_entry ON perfect_catalog.image_product_candidate (image_archive_entry_id);
CREATE INDEX ix_image_product_candidate_product ON perfect_catalog.image_product_candidate (product_template_id, product_variant_id);
CREATE INDEX ix_image_product_decision_value ON perfect_catalog.image_product_decision (decision, decided_at DESC);

CREATE TRIGGER trg_image_product_candidate_append_only BEFORE UPDATE OR DELETE ON perfect_catalog.image_product_candidate
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
CREATE TRIGGER trg_image_product_decision_append_only BEFORE UPDATE OR DELETE ON perfect_catalog.image_product_decision
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

REVOKE ALL ON perfect_catalog.image_product_candidate, perfect_catalog.image_product_decision
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;
GRANT SELECT, INSERT ON perfect_catalog.image_product_candidate, perfect_catalog.image_product_decision TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.image_product_candidate, perfect_catalog.image_product_decision TO perfect_catalog_readonly;

COMMIT;
