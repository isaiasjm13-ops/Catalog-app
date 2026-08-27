\set ON_ERROR_STOP on

SELECT (to_regclass('perfect_catalog.import_plan') IS NOT NULL) AS base_ready
\gset
\if :base_ready
\else
\echo 'ERROR: el esquema base no existe. Usa LIMPIAR-IMPORTACIONES solo si deseas reconstruirlo.'
\quit 3
\endif

SET ROLE perfect_catalog_owner;

SELECT (to_regclass('perfect_catalog.intake_submission') IS NULL) AS need_0007 \gset
\if :need_0007
\echo 'Aplicando 0007 - ingresos seguros'
\ir ../migrations/0007_secure_intake.sql
\endif

SELECT (to_regclass('perfect_catalog.intake_promotion') IS NULL) AS need_0008 \gset
\if :need_0008
\echo 'Aplicando 0008 - promocion de ingresos'
\ir ../migrations/0008_intake_promotion.sql
\endif

SELECT (to_regclass('perfect_catalog.image_archive_index') IS NULL) AS need_0009 \gset
\if :need_0009
\echo 'Aplicando 0009 - indice de imagenes'
\ir ../migrations/0009_image_archive_index.sql
\endif

SELECT (to_regclass('perfect_catalog.image_product_candidate') IS NULL) AS need_0010 \gset
\if :need_0010
\echo 'Aplicando 0010 - revision de imagenes'
\ir ../migrations/0010_image_match_review.sql
\endif

SELECT (to_regclass('perfect_catalog.approved_image_materialization') IS NULL) AS need_0011 \gset
\if :need_0011
\echo 'Aplicando 0011 - materializacion de imagenes'
\ir ../migrations/0011_approved_image_materialization.sql
\endif

\echo 'Verificando 0012 - permisos de aplicaciones vehiculares'
\ir ../migrations/0012_vehicle_application_workflow.sql

SELECT (to_regclass('perfect_catalog.brand_profile') IS NULL) AS need_0013 \gset
\if :need_0013
\echo 'Aplicando 0013 - perfiles de marca'
\ir ../migrations/0013_brand_profiles.sql
\endif

SELECT (NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='perfect_catalog' AND table_name='import_plan'
      AND column_name='brand_profile_id'
)) AS need_0014 \gset
\if :need_0014
\echo 'Aplicando 0014 - marca por importacion y catalogo'
\ir ../migrations/0014_brand_profile_workflow.sql
\endif

SELECT (to_regclass('perfect_catalog.visual_identity_revision') IS NULL) AS need_0015 \gset
\if :need_0015
\echo 'Aplicando 0015 - logos e identidad visual'
\ir ../migrations/0015_visual_identity_assets.sql
\endif

RESET ROLE;
\echo 'Base de datos actualizada. No hay migraciones pendientes.'
