BEGIN;

CREATE TABLE perfect_catalog.image_archive_index (
    image_archive_index_id uuid NOT NULL,
    intake_submission_id uuid NOT NULL,
    intake_asset_id uuid NOT NULL,
    source_sha256 text NOT NULL,
    algorithm text NOT NULL,
    index_sha256 text NOT NULL,
    image_count integer NOT NULL,
    ambiguous_count integer NOT NULL,
    report jsonb NOT NULL,
    indexed_by text NOT NULL,
    reason text NOT NULL,
    indexed_at timestamptz NOT NULL,
    CONSTRAINT pk_image_archive_index PRIMARY KEY (image_archive_index_id),
    CONSTRAINT uq_image_archive_index_submission UNIQUE (intake_submission_id),
    CONSTRAINT fk_image_archive_index_submission_asset FOREIGN KEY (intake_submission_id, intake_asset_id)
        REFERENCES perfect_catalog.intake_submission (intake_submission_id, intake_asset_id) ON DELETE RESTRICT,
    CONSTRAINT fk_image_archive_index_asset_sha FOREIGN KEY (intake_asset_id, source_sha256)
        REFERENCES perfect_catalog.intake_asset (intake_asset_id, sha256) ON DELETE RESTRICT,
    CONSTRAINT ck_image_archive_index_sha CHECK (source_sha256 ~ '^[0-9a-f]{64}$' AND index_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_image_archive_index_algorithm CHECK (algorithm = 'quarantined-image-index-v1'),
    CONSTRAINT ck_image_archive_index_counts CHECK (image_count > 0 AND ambiguous_count BETWEEN 0 AND image_count),
    CONSTRAINT ck_image_archive_index_report CHECK (jsonb_typeof(report) = 'object'),
    CONSTRAINT ck_image_archive_index_actor CHECK (btrim(indexed_by) <> '' AND char_length(indexed_by) <= 120),
    CONSTRAINT ck_image_archive_index_reason CHECK (char_length(btrim(reason)) BETWEEN 4 AND 500)
);

CREATE TABLE perfect_catalog.image_archive_entry (
    image_archive_entry_id uuid NOT NULL,
    image_archive_index_id uuid NOT NULL,
    entry_order integer NOT NULL,
    member_path text NOT NULL,
    original_filename text NOT NULL,
    extension text NOT NULL,
    media_type text NOT NULL,
    uncompressed_size bigint NOT NULL,
    compressed_size bigint NOT NULL,
    crc32 char(8) NOT NULL,
    content_sha256 char(64) NOT NULL,
    lookup_key text NOT NULL,
    match_status text NOT NULL,
    conflict_count integer NOT NULL,
    indexed_at timestamptz NOT NULL,
    CONSTRAINT pk_image_archive_entry PRIMARY KEY (image_archive_entry_id),
    CONSTRAINT fk_image_archive_entry_index FOREIGN KEY (image_archive_index_id)
        REFERENCES perfect_catalog.image_archive_index (image_archive_index_id) ON DELETE RESTRICT,
    CONSTRAINT uq_image_archive_entry_order UNIQUE (image_archive_index_id, entry_order),
    CONSTRAINT uq_image_archive_entry_path UNIQUE (image_archive_index_id, member_path),
    CONSTRAINT ck_image_archive_entry_order CHECK (entry_order > 0),
    CONSTRAINT ck_image_archive_entry_path CHECK (btrim(member_path) <> '' AND char_length(member_path) <= 500),
    CONSTRAINT ck_image_archive_entry_name CHECK (btrim(original_filename) <> '' AND char_length(original_filename) <= 240),
    CONSTRAINT ck_image_archive_entry_extension CHECK (extension ~ '^\.[a-z0-9]{1,12}$'),
    CONSTRAINT ck_image_archive_entry_media CHECK (btrim(media_type) <> ''),
    CONSTRAINT ck_image_archive_entry_sizes CHECK (uncompressed_size >= 0 AND compressed_size >= 0),
    CONSTRAINT ck_image_archive_entry_crc CHECK (crc32 ~ '^[0-9a-f]{8}$'),
    CONSTRAINT ck_image_archive_entry_sha CHECK (content_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_image_archive_entry_key CHECK (lookup_key ~ '^[A-Z0-9]+(?:-[A-Z0-9]+)*$'),
    CONSTRAINT ck_image_archive_entry_status CHECK (match_status IN ('unmatched', 'ambiguous')),
    CONSTRAINT ck_image_archive_entry_conflict CHECK (
        (match_status='unmatched' AND conflict_count=1) OR
        (match_status='ambiguous' AND conflict_count > 1)
    )
);

CREATE INDEX ix_image_archive_entry_lookup ON perfect_catalog.image_archive_entry (lookup_key, image_archive_index_id);
CREATE INDEX ix_image_archive_entry_sha ON perfect_catalog.image_archive_entry (content_sha256);

CREATE TRIGGER trg_image_archive_index_append_only BEFORE UPDATE OR DELETE ON perfect_catalog.image_archive_index
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();
CREATE TRIGGER trg_image_archive_entry_append_only BEFORE UPDATE OR DELETE ON perfect_catalog.image_archive_entry
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

REVOKE ALL ON perfect_catalog.image_archive_index, perfect_catalog.image_archive_entry
FROM PUBLIC, perfect_catalog_app, perfect_catalog_readonly;
GRANT SELECT, INSERT ON perfect_catalog.image_archive_index, perfect_catalog.image_archive_entry TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.image_archive_index, perfect_catalog.image_archive_entry TO perfect_catalog_readonly;

COMMIT;
