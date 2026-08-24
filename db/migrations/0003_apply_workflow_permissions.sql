BEGIN;

-- The source export may omit the informational variant count. NULL preserves
-- that absence instead of inventing zero.
ALTER TABLE perfect_catalog.product_template
    ALTER COLUMN variant_count_observed DROP NOT NULL;

-- The application role can transition reviewed plans and write only the
-- business records produced by an approved plan. DELETE remains ungranted.
REVOKE UPDATE ON perfect_catalog.source_system FROM perfect_catalog_app;
REVOKE UPDATE ON perfect_catalog.import_batch FROM perfect_catalog_app;

GRANT UPDATE (name, system_type, updated_at)
ON perfect_catalog.source_system TO perfect_catalog_app;

GRANT UPDATE (status, approved_by, finished_at, statistics)
ON perfect_catalog.import_batch TO perfect_catalog_app;

GRANT UPDATE (plan_status, approved_at, approved_by, applied_at, applied_by)
ON perfect_catalog.import_plan TO perfect_catalog_app;

GRANT INSERT ON
    perfect_catalog.brand,
    perfect_catalog.product_category,
    perfect_catalog.product_template,
    perfect_catalog.product_reference,
    perfect_catalog.inventory_snapshot,
    perfect_catalog.audit_event
TO perfect_catalog_app;

COMMIT;
