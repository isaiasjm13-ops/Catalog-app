\set ON_ERROR_STOP on
\pset pager off
\pset border 2
\pset null '(NULL)'

\echo 'AUDITORIA DE SOLO LECTURA: COMPANIES Y SU ASIGNACION DE BRANDS'
SELECT current_database() AS database_name, CURRENT_TIMESTAMP AS inspected_at;

\echo '--- Companies (activas e inactivas) ---'
SELECT company_id, code, display_name, is_active, created_at, updated_at
FROM perfect_catalog.company
ORDER BY is_active DESC, code;

\echo '--- Brands y la Company a la que pertenecen ahora mismo ---'
SELECT b.code AS brand_code, b.name AS brand_name, b.is_active AS brand_active,
       c.code AS company_code, c.display_name AS company_name, c.is_active AS company_active,
       b.brand_profile_id IS NOT NULL AS tiene_perfil_vinculado
FROM perfect_catalog.brand AS b
JOIN perfect_catalog.company AS c ON c.company_id = b.company_id
ORDER BY c.code, b.code;

\echo '--- Cuantos productos activos tiene cada Brand (para medir el impacto de mover una) ---'
SELECT c.code AS company_code, b.code AS brand_code, count(p.product_template_id) AS productos
FROM perfect_catalog.brand AS b
JOIN perfect_catalog.company AS c ON c.company_id = b.company_id
LEFT JOIN perfect_catalog.product_template AS p ON p.brand_id = b.brand_id
GROUP BY c.code, b.code
ORDER BY c.code, b.code;

\echo '--- Historial de administracion de Companies (altas/bajas auditadas, si existe la tabla) ---'
SELECT action, code_snapshot, display_name_snapshot, actor, reason, created_at
FROM perfect_catalog.company_admin_event
ORDER BY created_at DESC
LIMIT 50;

\echo 'AUDITORIA COMPLETADA EN SOLO LECTURA. NO SE MODIFICO NADA.'
