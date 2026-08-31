\set ON_ERROR_STOP on

\echo 'Eliminando solamente el esquema de datos de Perfect Catalog...'
SET ROLE perfect_catalog_owner;
DROP SCHEMA IF EXISTS perfect_catalog CASCADE;
RESET ROLE;

\echo 'Reconstruyendo el esquema y aplicando migraciones 0001-0018...'
\ir apply_initial_schema.sql
SET ROLE perfect_catalog_owner;
\ir ../migrations/0002_plan_future_product_targets.sql
\ir ../migrations/0003_apply_workflow_permissions.sql
\ir ../migrations/0004_restore_application_reads.sql
\ir ../migrations/0005_release_publication_workflow.sql
\ir ../migrations/0006_product_review_workflow.sql
\ir ../migrations/0007_secure_intake.sql
\ir ../migrations/0008_intake_promotion.sql
\ir ../migrations/0009_image_archive_index.sql
\ir ../migrations/0010_image_match_review.sql
\ir ../migrations/0011_approved_image_materialization.sql
\ir ../migrations/0012_vehicle_application_workflow.sql
\ir ../migrations/0013_brand_profiles.sql
\ir ../migrations/0014_brand_profile_workflow.sql
\ir ../migrations/0015_visual_identity_assets.sql
\ir ../migrations/0016_vehicle_make_visual_identity.sql
\ir ../migrations/0017_migration_ledger.sql
\ir ../migrations/0018_companies.sql
RESET ROLE;

\echo 'Esquema limpio y actualizado.'
