BEGIN;

CREATE TABLE perfect_catalog.visual_identity_revision (
    visual_identity_revision_id uuid PRIMARY KEY,
    scope text NOT NULL CHECK (scope IN ('company', 'brand')),
    brand_profile_id uuid REFERENCES perfect_catalog.brand_profile (brand_profile_id) ON DELETE RESTRICT,
    display_name text NOT NULL CHECK (btrim(display_name) <> ''),
    primary_color char(7) NOT NULL CHECK (primary_color ~ '^#[0-9A-F]{6}$'),
    secondary_color char(7) NOT NULL CHECK (secondary_color ~ '^#[0-9A-F]{6}$'),
    ink_color char(7) NOT NULL CHECK (ink_color ~ '^#[0-9A-F]{6}$'),
    paper_color char(7) NOT NULL CHECK (paper_color ~ '^#[0-9A-F]{6}$'),
    logo_sha256 char(64) NOT NULL CHECK (logo_sha256 ~ '^[0-9a-f]{64}$'),
    logo_media_type text NOT NULL CHECK (logo_media_type IN ('image/png','image/jpeg','image/svg+xml')),
    logo_storage_relpath text NOT NULL CHECK (logo_storage_relpath ~ '^objects/[0-9a-f]{2}/[0-9a-f]{64}[.](png|jpg|svg)$'),
    original_filename text NOT NULL CHECK (btrim(original_filename) <> ''),
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by text NOT NULL CHECK (btrim(created_by) <> ''),
    creation_reason text NOT NULL CHECK (length(btrim(creation_reason)) BETWEEN 4 AND 500),
    CHECK ((scope='company' AND brand_profile_id IS NULL) OR (scope='brand' AND brand_profile_id IS NOT NULL))
);

CREATE INDEX ix_visual_identity_revision_latest
ON perfect_catalog.visual_identity_revision (scope, brand_profile_id, created_at DESC);

REVOKE ALL ON perfect_catalog.visual_identity_revision FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.visual_identity_revision TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.visual_identity_revision TO perfect_catalog_readonly;

COMMIT;
