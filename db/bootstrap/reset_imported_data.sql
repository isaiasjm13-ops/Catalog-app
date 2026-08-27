\set ON_ERROR_STOP on

\echo 'Eliminando solamente el esquema de datos de Perfect Catalog...'
SET ROLE perfect_catalog_owner;
DROP SCHEMA IF EXISTS perfect_catalog CASCADE;
RESET ROLE;

\echo 'Reconstruyendo el esquema y aplicando migraciones 0001-0012...'
\ir apply_initial_schema.sql
\ir apply_followup_migration.sql
\ir apply_apply_workflow_migration.sql
\ir apply_application_reads_migration.sql
\ir apply_release_publication_migration.sql
\ir apply_product_review_migration.sql
\ir apply_intake_migration.sql
\ir apply_intake_promotion_migration.sql
\ir apply_image_archive_index_migration.sql
\ir apply_image_match_review_migration.sql
\ir apply_approved_image_materialization_migration.sql
\ir apply_vehicle_application_workflow_migration.sql
\ir apply_brand_profiles_migration.sql
\ir apply_brand_profile_workflow_migration.sql
\ir apply_pending_migrations.sql

\echo 'Esquema limpio y actualizado.'
