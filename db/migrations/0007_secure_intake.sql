BEGIN;

CREATE TABLE perfect_catalog.intake_asset (
    intake_asset_id uuid NOT NULL,
    sha256 text NOT NULL,
    size_bytes bigint NOT NULL,
    detected_media_type text NOT NULL,
    storage_relpath text NOT NULL,
    received_at timestamp with time zone NOT NULL,
    received_by text NOT NULL,
    CONSTRAINT pk_intake_asset PRIMARY KEY (intake_asset_id),
    CONSTRAINT uq_intake_asset_sha256 UNIQUE (sha256),
    CONSTRAINT uq_intake_asset_storage UNIQUE (storage_relpath),
    CONSTRAINT ck_intake_asset_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_intake_asset_size CHECK (size_bytes > 0),
    CONSTRAINT ck_intake_asset_media_nonempty CHECK (
        btrim(detected_media_type) <> '' AND char_length(detected_media_type) <= 120
    ),
    CONSTRAINT ck_intake_asset_storage CHECK (
        storage_relpath ~ '^quarantine/objects/[0-9a-f]{2}/[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_intake_asset_actor_nonempty CHECK (
        btrim(received_by) <> '' AND char_length(received_by) <= 120
    )
);

CREATE TABLE perfect_catalog.intake_submission (
    intake_submission_id uuid NOT NULL,
    intake_asset_id uuid,
    intake_kind text NOT NULL,
    original_name text NOT NULL,
    extension text NOT NULL,
    claimed_media_type text,
    detected_media_type text NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 text NOT NULL,
    validation_status text NOT NULL,
    duplicate_content boolean NOT NULL,
    validation_report jsonb NOT NULL,
    submitted_by text NOT NULL,
    reason text NOT NULL,
    submitted_at timestamp with time zone NOT NULL,
    CONSTRAINT pk_intake_submission PRIMARY KEY (intake_submission_id),
    CONSTRAINT fk_intake_submission_asset FOREIGN KEY (intake_asset_id)
        REFERENCES perfect_catalog.intake_asset (intake_asset_id) ON DELETE RESTRICT,
    CONSTRAINT ck_intake_submission_kind CHECK (
        intake_kind IN ('odoo_data', 'image_archive', 'manual_pdf', 'indesign_package')
    ),
    CONSTRAINT ck_intake_submission_name_nonempty CHECK (
        btrim(original_name) <> '' AND char_length(original_name) <= 240
    ),
    CONSTRAINT ck_intake_submission_extension CHECK (extension ~ '^\.[a-z0-9]{1,12}$'),
    CONSTRAINT ck_intake_submission_claimed_media CHECK (
        claimed_media_type IS NULL OR (
            btrim(claimed_media_type) <> '' AND char_length(claimed_media_type) <= 120
        )
    ),
    CONSTRAINT ck_intake_submission_detected_media CHECK (
        btrim(detected_media_type) <> '' AND char_length(detected_media_type) <= 120
    ),
    CONSTRAINT ck_intake_submission_size CHECK (size_bytes > 0),
    CONSTRAINT ck_intake_submission_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_intake_submission_status CHECK (
        validation_status IN ('quarantined', 'rejected')
    ),
    CONSTRAINT ck_intake_submission_asset_alignment CHECK (
        (validation_status = 'quarantined' AND intake_asset_id IS NOT NULL)
        OR (validation_status = 'rejected' AND intake_asset_id IS NULL)
    ),
    CONSTRAINT ck_intake_submission_duplicate_alignment CHECK (
        validation_status = 'quarantined' OR duplicate_content = false
    ),
    CONSTRAINT ck_intake_submission_report_object CHECK (
        jsonb_typeof(validation_report) = 'object'
    ),
    CONSTRAINT ck_intake_submission_actor_nonempty CHECK (
        btrim(submitted_by) <> '' AND char_length(submitted_by) <= 120
    ),
    CONSTRAINT ck_intake_submission_reason_nonempty CHECK (
        char_length(btrim(reason)) BETWEEN 4 AND 500
    )
);

CREATE INDEX ix_intake_submission_submitted
    ON perfect_catalog.intake_submission (submitted_at DESC, intake_submission_id DESC);
CREATE INDEX ix_intake_submission_kind_status
    ON perfect_catalog.intake_submission (intake_kind, validation_status, submitted_at DESC);

CREATE TRIGGER trg_intake_asset_append_only
BEFORE UPDATE OR DELETE ON perfect_catalog.intake_asset
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

CREATE TRIGGER trg_intake_submission_append_only
BEFORE UPDATE OR DELETE ON perfect_catalog.intake_submission
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

REVOKE ALL
ON perfect_catalog.intake_asset, perfect_catalog.intake_submission
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;

GRANT SELECT, INSERT
ON perfect_catalog.intake_asset, perfect_catalog.intake_submission
TO perfect_catalog_app;

GRANT SELECT
ON perfect_catalog.intake_asset, perfect_catalog.intake_submission
TO perfect_catalog_readonly;

COMMIT;
