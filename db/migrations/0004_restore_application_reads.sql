BEGIN;

-- The application serves the catalog, builds dry-runs, and verifies persisted
-- plans before approval/apply. Restore only its currently required reads so
-- upgraded databases cannot retain permission drift.
GRANT SELECT ON
    perfect_catalog.source_system,
    perfect_catalog.import_batch,
    perfect_catalog.import_file,
    perfect_catalog.staging_row,
    perfect_catalog.staging_row_result,
    perfect_catalog.import_issue,
    perfect_catalog.import_plan,
    perfect_catalog.import_plan_item,
    perfect_catalog.brand,
    perfect_catalog.product_category,
    perfect_catalog.product_template,
    perfect_catalog.product_variant,
    perfect_catalog.product_reference,
    perfect_catalog.inventory_snapshot,
    perfect_catalog.media_asset,
    perfect_catalog.product_media,
    perfect_catalog.catalog_release,
    perfect_catalog.catalog_release_item
TO perfect_catalog_app;

COMMIT;
