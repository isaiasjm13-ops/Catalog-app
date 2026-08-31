\set ON_ERROR_STOP on
\pset pager off
\pset border 2
\pset null '(NULL)'

\echo 'PERFECT CATALOG - AUDITORIA PRE-MULTIEMPRESA'
SELECT current_database() AS database_name,
       current_user AS database_user,
       current_setting('server_version') AS postgres_version,
       CURRENT_TIMESTAMP AS inspected_at;

\echo '--- Esquema y tablas principales ---'
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'perfect_catalog' AND table_type = 'BASE TABLE'
ORDER BY table_name;

\echo '--- Presencia estructural de migraciones 0001-0016 ---'
SELECT '0001 base' AS migration, to_regclass('perfect_catalog.product_template') IS NOT NULL AS present
UNION ALL SELECT '0005 releases', to_regclass('perfect_catalog.catalog_release') IS NOT NULL
UNION ALL SELECT '0007 intake', to_regclass('perfect_catalog.intake_submission') IS NOT NULL
UNION ALL SELECT '0008 promotion', to_regclass('perfect_catalog.intake_promotion') IS NOT NULL
UNION ALL SELECT '0009 image index', to_regclass('perfect_catalog.image_archive_index') IS NOT NULL
UNION ALL SELECT '0010 image review', to_regclass('perfect_catalog.image_product_candidate') IS NOT NULL
UNION ALL SELECT '0011 materialization', to_regclass('perfect_catalog.approved_image_materialization') IS NOT NULL
UNION ALL SELECT '0012 vehicle applications', to_regclass('perfect_catalog.product_application_candidate') IS NOT NULL
UNION ALL SELECT '0013 brand profile', to_regclass('perfect_catalog.brand_profile') IS NOT NULL
UNION ALL SELECT '0014 brand workflow', EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema='perfect_catalog'
      AND table_name='brand' AND column_name='brand_profile_id')
UNION ALL SELECT '0015 visual identity', to_regclass('perfect_catalog.visual_identity_revision') IS NOT NULL
UNION ALL SELECT '0016 vehicle identity', EXISTS (
    SELECT 1 FROM information_schema.columns WHERE table_schema='perfect_catalog'
      AND table_name='visual_identity_revision' AND column_name='vehicle_make_id')
ORDER BY migration;

\echo '--- Cardinalidades de negocio ---'
SELECT 'brand' AS entity, count(*) AS row_count FROM perfect_catalog.brand
UNION ALL SELECT 'product_category', count(*) FROM perfect_catalog.product_category
UNION ALL SELECT 'product_template', count(*) FROM perfect_catalog.product_template
UNION ALL SELECT 'product_variant', count(*) FROM perfect_catalog.product_variant
UNION ALL SELECT 'product_reference', count(*) FROM perfect_catalog.product_reference
UNION ALL SELECT 'catalog_release', count(*) FROM perfect_catalog.catalog_release
UNION ALL SELECT 'catalog_release_item', count(*) FROM perfect_catalog.catalog_release_item
UNION ALL SELECT 'visual_identity_revision', count(*) FROM perfect_catalog.visual_identity_revision
ORDER BY entity;

\echo '--- Marcas y perfiles actuales ---'
SELECT b.brand_id, b.code, b.name, b.normalized_name, b.is_active,
       b.source_system_id, b.brand_profile_id, bp.code AS profile_code,
       bp.display_name AS profile_name
FROM perfect_catalog.brand AS b
LEFT JOIN perfect_catalog.brand_profile AS bp USING (brand_profile_id)
ORDER BY b.normalized_name, b.brand_id;

\echo '--- Productos por marca y estado ---'
SELECT b.code AS brand_code, b.name AS brand_name, p.catalog_status, count(*) AS products
FROM perfect_catalog.product_template AS p
JOIN perfect_catalog.brand AS b USING (brand_id)
GROUP BY b.code, b.name, p.catalog_status
ORDER BY b.code, p.catalog_status;

\echo '--- Releases por marca y estado ---'
SELECT b.code AS brand_code, r.status, count(*) AS releases,
       min(r.created_at) AS first_release, max(r.created_at) AS last_release
FROM perfect_catalog.catalog_release AS r
JOIN perfect_catalog.brand AS b USING (brand_id)
GROUP BY b.code, r.status
ORDER BY b.code, r.status;

\echo '--- Identidades visuales por scope ---'
SELECT scope, count(*) AS revisions, min(created_at) AS first_revision,
       max(created_at) AS last_revision
FROM perfect_catalog.visual_identity_revision
GROUP BY scope ORDER BY scope;

\echo '--- Calidad de referencias ---'
SELECT reference_type, review_status, count(*) AS references
FROM perfect_catalog.product_reference
GROUP BY reference_type, review_status
ORDER BY reference_type, review_status NULLS FIRST;

\echo '--- Posibles duplicados normalizados entre productos ---'
SELECT value_normalized, count(DISTINCT product_template_id) AS products,
       count(*) AS occurrences
FROM perfect_catalog.product_reference
GROUP BY value_normalized
HAVING count(DISTINCT product_template_id) > 1
ORDER BY products DESC, occurrences DESC, value_normalized
LIMIT 100;

\echo '--- Privilegios de roles de aplicacion ---'
SELECT grantee, privilege_type, count(*) AS grants
FROM information_schema.role_table_grants
WHERE table_schema='perfect_catalog'
  AND grantee IN ('perfect_catalog_app', 'perfect_catalog_readonly', 'perfect_catalog_owner')
GROUP BY grantee, privilege_type
ORDER BY grantee, privilege_type;

\echo 'AUDITORIA COMPLETADA EN SOLO LECTURA.'
