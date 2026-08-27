BEGIN;

-- Materializa las sugerencias del parser durante apply y permite que la misma
-- decisión humana de identidad resuelva sus aplicaciones visibles.
GRANT INSERT ON
    perfect_catalog.vehicle_make,
    perfect_catalog.vehicle_model,
    perfect_catalog.product_application_candidate
TO perfect_catalog_app;

GRANT UPDATE (review_status, reviewed_by, reviewed_at, review_note, updated_at)
ON perfect_catalog.vehicle_make TO perfect_catalog_app;

GRANT UPDATE (review_status, reviewed_by, reviewed_at, review_note, updated_at)
ON perfect_catalog.vehicle_model TO perfect_catalog_app;

GRANT UPDATE (review_status, reviewed_by, reviewed_at, review_note)
ON perfect_catalog.product_application_candidate TO perfect_catalog_app;

COMMIT;
