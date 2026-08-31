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

SELECT (NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='perfect_catalog' AND table_name='visual_identity_revision'
      AND column_name='vehicle_make_id'
)) AS need_0016 \gset
\if :need_0016
\echo 'Aplicando 0016 - logos de marcas vehiculares'
\ir ../migrations/0016_vehicle_make_visual_identity.sql
\endif

SELECT (to_regclass('perfect_catalog.schema_migration') IS NULL) AS need_0017 \gset
\if :need_0017
\echo 'Aplicando 0017 - ledger de migraciones con checksum'
\ir ../migrations/0017_migration_ledger.sql
\else
SELECT COALESCE((SELECT checksum_sha256 <> :'checksum_0017'
FROM perfect_catalog.schema_migration WHERE migration_id='0017_migration_ledger'), true) AS mismatch_0017 \gset
\if :mismatch_0017
\echo 'ERROR: checksum distinto para 0017_migration_ledger.'
\quit 3
\endif
\endif

SELECT (to_regclass('perfect_catalog.company') IS NULL) AS need_0018 \gset
\if :need_0018
\echo 'Aplicando 0018 - Companies y pertenencia de Brand'
\ir ../migrations/0018_companies.sql
\else
SELECT COALESCE((SELECT checksum_sha256 <> :'checksum_0018'
FROM perfect_catalog.schema_migration WHERE migration_id='0018_companies'), true) AS mismatch_0018 \gset
\if :mismatch_0018
\echo 'ERROR: checksum distinto para 0018_companies.'
\quit 3
\endif
\endif

SELECT (NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='perfect_catalog' AND table_name='visual_identity_revision'
      AND column_name='company_id'
)) AS need_0019 \gset
\if :need_0019
\echo 'Aplicando 0019 - identidad corporativa por Company'
\ir ../migrations/0019_company_visual_identity.sql
\else
SELECT COALESCE((SELECT checksum_sha256 <> :'checksum_0019'
FROM perfect_catalog.schema_migration WHERE migration_id='0019_company_visual_identity'), true) AS mismatch_0019 \gset
\if :mismatch_0019
\echo 'ERROR: checksum distinto para 0019_company_visual_identity.'
\quit 3
\endif
\endif

SELECT (NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='perfect_catalog' AND table_name='intake_submission'
      AND column_name='company_id'
)) AS need_0020 \gset
\if :need_0020
\echo 'Aplicando 0020 - Company desde ingreso hasta plan'
\ir ../migrations/0020_company_intake_context.sql
\else
SELECT COALESCE((SELECT checksum_sha256 <> :'checksum_0020'
FROM perfect_catalog.schema_migration WHERE migration_id='0020_company_intake_context'), true) AS mismatch_0020 \gset
\if :mismatch_0020
\echo 'ERROR: checksum distinto para 0020_company_intake_context.'
\quit 3
\endif
\endif

\echo 'Validando ledger 0017-0020 y contexto Company'
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0017_migration_ledger'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0018_companies'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0019_company_visual_identity'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0020_company_intake_context'
    ) THEN
        RAISE EXCEPTION 'Validacion multiempresa: faltan entradas 0017-0020 en el ledger';
    END IF;

    IF EXISTS (
        SELECT 1 FROM perfect_catalog.import_plan
        WHERE brand_profile_id IS NOT NULL AND company_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Validacion multiempresa: plan con marca pero sin Company';
    END IF;

    IF EXISTS (
        SELECT 1 FROM perfect_catalog.visual_identity_revision
        WHERE (scope = 'company') <> (company_id IS NOT NULL)
    ) THEN
        RAISE EXCEPTION 'Validacion multiempresa: identidad corporativa sin Company exacta';
    END IF;

    IF (SELECT count(*) FROM perfect_catalog.company) < 5 THEN
        RAISE EXCEPTION 'Validacion multiempresa: faltan Companies iniciales';
    END IF;

    IF EXISTS (SELECT 1 FROM perfect_catalog.brand WHERE company_id IS NULL) THEN
        RAISE EXCEPTION 'Validacion multiempresa: existen marcas sin Company';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM perfect_catalog.brand AS b
        JOIN perfect_catalog.company AS c ON c.company_id = b.company_id
        WHERE (b.code = 'EXACTCARS' AND c.code <> 'PERFECT')
           OR (b.code = 'NATSUKI' AND c.code <> 'NATSUKI')
    ) THEN
        RAISE EXCEPTION 'Validacion multiempresa: mapping inicial incorrecto';
    END IF;
END
$$;

SELECT c.code AS company, count(b.brand_id) AS brands
FROM perfect_catalog.company AS c
LEFT JOIN perfect_catalog.brand AS b ON b.company_id = c.company_id
GROUP BY c.code
ORDER BY c.code;

RESET ROLE;
\echo 'Base de datos actualizada y validada. No hay migraciones pendientes.'
