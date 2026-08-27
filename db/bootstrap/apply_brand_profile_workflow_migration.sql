\set ON_ERROR_STOP on
SET ROLE perfect_catalog_owner;

SELECT (to_regclass('perfect_catalog.brand_profile') IS NULL) AS need_0013
\gset
\if :need_0013
\echo 'La tabla brand_profile no existe; aplicando primero la migracion 0013.'
\ir ../migrations/0013_brand_profiles.sql
\else
\echo 'Migracion 0013 ya presente; continuando.'
\endif

SELECT (NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='perfect_catalog'
      AND table_name='import_plan'
      AND column_name='brand_profile_id'
)) AS need_0014
\gset
\if :need_0014
\ir ../migrations/0014_brand_profile_workflow.sql
\else
\echo 'Migracion 0014 ya presente; no hay cambios pendientes.'
\endif

RESET ROLE;
