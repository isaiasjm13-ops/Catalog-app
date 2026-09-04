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
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0019_company_visual_identity') AS ledger_0019 \gset
\if :ledger_0019
SELECT checksum_sha256 <> :'checksum_0019' AS mismatch_0019 FROM perfect_catalog.schema_migration WHERE migration_id='0019_company_visual_identity' \gset
\if :mismatch_0019
\echo 'CHECKSUM_MISMATCH: 0019_company_visual_identity.'
\quit 3
\endif
\else
\if :need_0019
\echo 'MIGRATION_PENDING: 0019 - identidad corporativa por Company'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0019; validando postcondiciones.'
\endif
\ir ../migrations/0019_company_visual_identity.sql
\endif

SELECT (NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='perfect_catalog' AND table_name='intake_submission'
      AND column_name='company_id'
)) AS need_0020 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0020_company_intake_context') AS ledger_0020 \gset
\if :ledger_0020
SELECT checksum_sha256 <> :'checksum_0020' AS mismatch_0020 FROM perfect_catalog.schema_migration WHERE migration_id='0020_company_intake_context' \gset
\if :mismatch_0020
\echo 'CHECKSUM_MISMATCH: 0020_company_intake_context.'
\quit 3
\endif
\else
\if :need_0020
\echo 'MIGRATION_PENDING: 0020 - Company desde ingreso hasta plan'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0020; validando postcondiciones.'
\endif
\ir ../migrations/0020_company_intake_context.sql
\endif

SELECT (to_regclass('perfect_catalog.company_admin_event') IS NULL) AS need_0021 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0021_company_administration') AS ledger_0021 \gset
\if :ledger_0021
SELECT checksum_sha256 <> :'checksum_0021' AS mismatch_0021 FROM perfect_catalog.schema_migration WHERE migration_id='0021_company_administration' \gset
\if :mismatch_0021
\echo 'CHECKSUM_MISMATCH: 0021_company_administration.'
\quit 3
\endif
\else
\if :need_0021
\echo 'MIGRATION_PENDING: 0021 - administracion y correccion de Companies'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0021; validando postcondiciones.'
\endif
\ir ../migrations/0021_company_administration.sql
\endif


SELECT (to_regprocedure('perfect_catalog.apply_controlled_product_update(uuid,uuid,text)') IS NULL) AS need_0022 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0022_controlled_product_updates') AS ledger_0022 \gset
\if :ledger_0022
SELECT checksum_sha256 <> :'checksum_0022' AS mismatch_0022 FROM perfect_catalog.schema_migration WHERE migration_id='0022_controlled_product_updates' \gset
\if :mismatch_0022
\echo 'CHECKSUM_MISMATCH: 0022_controlled_product_updates.'
\quit 3
\endif
\else
\if :need_0022
\echo 'MIGRATION_PENDING: 0022 - UPDATE controlado de productos'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0022; validando postcondiciones.'
\endif
\ir ../migrations/0022_controlled_product_updates.sql
\endif


SELECT (to_regclass('perfect_catalog.brand_profile_link_event') IS NULL) AS need_0023 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0023_brand_profile_linking') AS ledger_0023 \gset
\if :ledger_0023
SELECT checksum_sha256 <> :'checksum_0023' AS mismatch_0023 FROM perfect_catalog.schema_migration WHERE migration_id='0023_brand_profile_linking' \gset
\if :mismatch_0023
\echo 'CHECKSUM_MISMATCH: 0023_brand_profile_linking.'
\quit 3
\endif
\else
\if :need_0023
\echo 'MIGRATION_PENDING: 0023 - vinculo auditado Brand -> Brand Profile'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0023; validando postcondiciones.'
\endif
\ir ../migrations/0023_brand_profile_linking.sql
\endif


SELECT (to_regclass('perfect_catalog.intake_submission_archive_event') IS NULL) AS need_0024 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0024_intake_submission_archiving') AS ledger_0024 \gset
\if :ledger_0024
SELECT checksum_sha256 <> :'checksum_0024' AS mismatch_0024 FROM perfect_catalog.schema_migration WHERE migration_id='0024_intake_submission_archiving' \gset
\if :mismatch_0024
\echo 'CHECKSUM_MISMATCH: 0024_intake_submission_archiving.'
\quit 3
\endif
\else
\if :need_0024
\echo 'MIGRATION_PENDING: 0024 - archivado auditado de ingresos'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0024; validando postcondiciones.'
\endif
\ir ../migrations/0024_intake_submission_archiving.sql
\endif


SELECT (
    EXISTS (SELECT 1 FROM perfect_catalog.company WHERE code='NATSUKI' AND is_active=false)
    OR EXISTS (
        SELECT 1 FROM perfect_catalog.brand AS b
        JOIN perfect_catalog.company AS c ON c.company_id=b.company_id
        WHERE b.code='NATSUKI' AND c.code <> 'NATSUKI'
    )
) AS need_0025 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0025_natsuki_company_restored') AS ledger_0025 \gset
\if :ledger_0025
SELECT checksum_sha256 <> :'checksum_0025' AS mismatch_0025 FROM perfect_catalog.schema_migration WHERE migration_id='0025_natsuki_company_restored' \gset
\if :mismatch_0025
\echo 'CHECKSUM_MISMATCH: 0025_natsuki_company_restored.'
\quit 3
\endif
\else
\if :need_0025
\echo 'MIGRATION_PENDING: 0025 - NATSUKI vuelve a ser Company propia'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0025; validando postcondiciones.'
\endif
\ir ../migrations/0025_natsuki_company_restored.sql
\endif


SELECT (to_regclass('perfect_catalog.approved_image_variant') IS NULL) AS need_0026 \gset
SELECT EXISTS (SELECT 1 FROM perfect_catalog.schema_migration WHERE migration_id='0026_product_photo_variants') AS ledger_0026 \gset
\if :ledger_0026
SELECT checksum_sha256 <> :'checksum_0026' AS mismatch_0026 FROM perfect_catalog.schema_migration WHERE migration_id='0026_product_photo_variants' \gset
\if :mismatch_0026
\echo 'CHECKSUM_MISMATCH: 0026_product_photo_variants.'
\quit 3
\endif
\else
\if :need_0026
\echo 'MIGRATION_PENDING: 0026 - fotos variantes por producto'
\else
\echo 'SCHEMA_AHEAD_OF_LEDGER: 0026; validando postcondiciones.'
\endif
\ir ../migrations/0026_product_photo_variants.sql
\endif

\echo 'Validando ledger 0017-0026 y contexto Company'
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
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0021_company_administration'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0022_controlled_product_updates'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0023_brand_profile_linking'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0024_intake_submission_archiving'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0025_natsuki_company_restored'
    ) OR NOT EXISTS (
        SELECT 1 FROM perfect_catalog.schema_migration
        WHERE migration_id = '0026_product_photo_variants'
    ) THEN
        RAISE EXCEPTION 'Validacion del sistema: faltan entradas 0017-0026 en el ledger';
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

    IF (SELECT count(*) FROM perfect_catalog.company WHERE is_active) < 3 THEN
        RAISE EXCEPTION 'Validacion multiempresa: faltan Companies activas iniciales';
    END IF;

    IF EXISTS (SELECT 1 FROM perfect_catalog.brand WHERE company_id IS NULL) THEN
        RAISE EXCEPTION 'Validacion multiempresa: existen marcas sin Company';
    END IF;

    IF to_regprocedure('perfect_catalog.apply_controlled_product_update(uuid,uuid,text)') IS NULL THEN
        RAISE EXCEPTION 'Validacion de UPDATE controlado: falta funcion 0022';
    END IF;

    IF NOT has_function_privilege('perfect_catalog_app', 'perfect_catalog.apply_controlled_product_update(uuid,uuid,text)', 'EXECUTE') THEN
        RAISE EXCEPTION 'Validacion de UPDATE controlado: app sin EXECUTE';
    END IF;

    IF has_table_privilege('perfect_catalog_app', 'perfect_catalog.product_template', 'UPDATE') THEN
        RAISE EXCEPTION 'Validacion de UPDATE controlado: app conserva UPDATE general';
    END IF;

    IF to_regclass('perfect_catalog.brand_profile_link_event') IS NULL THEN
        RAISE EXCEPTION 'Validacion de vinculo Brand-Perfil: falta tabla de auditoria 0023';
    END IF;

    IF NOT has_column_privilege('perfect_catalog_app', 'perfect_catalog.brand', 'brand_profile_id', 'UPDATE') THEN
        RAISE EXCEPTION 'Validacion de vinculo Brand-Perfil: app sin UPDATE en brand.brand_profile_id';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_brand_profile_link_event_append_only'
          AND tgrelid = 'perfect_catalog.brand_profile_link_event'::regclass
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Validacion de vinculo Brand-Perfil: falta guardia append-only 0023';
    END IF;

    IF to_regclass('perfect_catalog.intake_submission_archive_event') IS NULL THEN
        RAISE EXCEPTION 'Validacion de archivado de ingresos: falta tabla de auditoria 0024';
    END IF;

    IF has_table_privilege('perfect_catalog_app', 'perfect_catalog.intake_submission', 'UPDATE') THEN
        RAISE EXCEPTION 'Validacion de archivado de ingresos: intake_submission perdio su guardia append-only';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_intake_submission_archive_event_append_only'
          AND tgrelid = 'perfect_catalog.intake_submission_archive_event'::regclass
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Validacion de archivado de ingresos: falta guardia append-only 0024';
    END IF;

    IF EXISTS (
        SELECT 1
        FROM perfect_catalog.brand AS b
        JOIN perfect_catalog.company AS c ON c.company_id = b.company_id
        WHERE (b.code = 'EXACTCARS' AND c.code <> 'PERFECT')
           OR (b.code = 'MASAKI' AND c.code <> 'PERFECT')
           OR (b.code = 'NATSUKI' AND c.code <> 'NATSUKI')
    ) THEN
        RAISE EXCEPTION 'Validacion multiempresa: mapping inicial incorrecto';
    END IF;

    IF NOT EXISTS (SELECT 1 FROM perfect_catalog.company WHERE code='NATSUKI' AND is_active) THEN
        RAISE EXCEPTION 'Validacion 0025: NATSUKI debe existir como Company activa';
    END IF;

    IF to_regclass('perfect_catalog.approved_image_variant') IS NULL THEN
        RAISE EXCEPTION 'Validacion de fotos variantes: falta tabla 0026';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='perfect_catalog' AND table_name='image_product_candidate'
          AND column_name='variant_index'
    ) THEN
        RAISE EXCEPTION 'Validacion de fotos variantes: falta columna variant_index 0026';
    END IF;

    IF has_table_privilege('perfect_catalog_app', 'perfect_catalog.approved_image_variant', 'UPDATE') THEN
        RAISE EXCEPTION 'Validacion de fotos variantes: app conserva UPDATE sobre approved_image_variant';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_trigger
        WHERE tgname = 'trg_approved_image_variant_append_only'
          AND tgrelid = 'perfect_catalog.approved_image_variant'::regclass
          AND NOT tgisinternal
    ) THEN
        RAISE EXCEPTION 'Validacion de fotos variantes: falta guardia append-only 0026';
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
