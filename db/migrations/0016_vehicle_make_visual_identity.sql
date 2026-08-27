BEGIN;

ALTER TABLE perfect_catalog.visual_identity_revision
    ADD COLUMN vehicle_make_id uuid;

ALTER TABLE perfect_catalog.visual_identity_revision
    DROP CONSTRAINT visual_identity_revision_scope_check,
    DROP CONSTRAINT visual_identity_revision_check,
    ADD CONSTRAINT ck_visual_identity_revision_scope
        CHECK (scope IN ('company', 'brand', 'vehicle_make')),
    ADD CONSTRAINT fk_visual_identity_revision_vehicle_make
        FOREIGN KEY (vehicle_make_id)
        REFERENCES perfect_catalog.vehicle_make (vehicle_make_id)
        ON DELETE RESTRICT,
    ADD CONSTRAINT ck_visual_identity_revision_target
        CHECK (
            (scope='company' AND brand_profile_id IS NULL AND vehicle_make_id IS NULL)
            OR (scope='brand' AND brand_profile_id IS NOT NULL AND vehicle_make_id IS NULL)
            OR (scope='vehicle_make' AND brand_profile_id IS NULL AND vehicle_make_id IS NOT NULL)
        );

CREATE INDEX ix_visual_identity_revision_vehicle_make_latest
ON perfect_catalog.visual_identity_revision (vehicle_make_id, created_at DESC)
WHERE scope='vehicle_make';

COMMIT;
