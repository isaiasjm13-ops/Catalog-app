\set ON_ERROR_STOP on
\pset format unaligned
\pset fieldsep '|'
\pset tuples_only on

SELECT 'database' AS section, 'name' AS metric, datname AS value
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'owner', pg_get_userbyid(datdba)
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'encoding', pg_encoding_to_char(encoding)
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'locale_provider', datlocprovider::text
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'icu_locale', datlocale
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'collation_version', COALESCE(datcollversion, '')
FROM pg_database WHERE datname = current_database()
UNION ALL
SELECT 'database', 'timezone', current_setting('TimeZone')
UNION ALL
SELECT 'database', 'public_connect', has_database_privilege('public', current_database(), 'CONNECT')::text
UNION ALL
SELECT 'database', 'app_connect', has_database_privilege('perfect_catalog_app', current_database(), 'CONNECT')::text
UNION ALL
SELECT 'database', 'readonly_connect', has_database_privilege('perfect_catalog_readonly', current_database(), 'CONNECT')::text
UNION ALL
SELECT 'schema', 'owner', pg_get_userbyid(nspowner)
FROM pg_namespace WHERE nspname = 'perfect_catalog'
UNION ALL
SELECT 'schema', 'table_count', count(*)::text
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'perfect_catalog' AND c.relkind = 'r'
UNION ALL
SELECT 'schema', 'primary_key_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'p'
UNION ALL
SELECT 'schema', 'foreign_key_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'f'
UNION ALL
SELECT 'schema', 'check_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'c'
UNION ALL
SELECT 'schema', 'unique_constraint_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'u'
UNION ALL
SELECT 'schema', 'index_count', count(*)::text
FROM pg_class AS i
JOIN pg_namespace AS n ON n.oid = i.relnamespace
WHERE n.nspname = 'perfect_catalog' AND i.relkind = 'i'
UNION ALL
SELECT 'schema', 'generated_column_count', count(*)::text
FROM information_schema.columns
WHERE table_schema = 'perfect_catalog' AND is_generated = 'ALWAYS'
UNION ALL
SELECT 'schema', 'restrict_foreign_key_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'f' AND c.confdeltype = 'r'
UNION ALL
SELECT 'schema', 'cascade_foreign_key_count', count(*)::text
FROM pg_constraint AS c
JOIN pg_namespace AS n ON n.oid = c.connamespace
WHERE n.nspname = 'perfect_catalog' AND c.contype = 'f' AND c.confdeltype = 'c'
UNION ALL
SELECT 'schema', 'non_owner_table_count', count(*)::text
FROM pg_class AS c
JOIN pg_namespace AS n ON n.oid = c.relnamespace
WHERE n.nspname = 'perfect_catalog'
  AND c.relkind = 'r'
  AND pg_get_userbyid(c.relowner) <> 'perfect_catalog_owner'
ORDER BY 1, 2;

SELECT 'role', rolname, concat_ws(',',
    CASE WHEN rolcanlogin THEN 'LOGIN' ELSE 'NOLOGIN' END,
    CASE WHEN rolsuper THEN 'SUPERUSER' ELSE 'NOSUPERUSER' END,
    CASE WHEN rolcreatedb THEN 'CREATEDB' ELSE 'NOCREATEDB' END,
    CASE WHEN rolcreaterole THEN 'CREATEROLE' ELSE 'NOCREATEROLE' END,
    CASE WHEN rolreplication THEN 'REPLICATION' ELSE 'NOREPLICATION' END,
    CASE WHEN rolbypassrls THEN 'BYPASSRLS' ELSE 'NOBYPASSRLS' END
)
FROM pg_roles
WHERE rolname IN ('perfect_catalog_owner', 'perfect_catalog_app', 'perfect_catalog_readonly')
ORDER BY rolname;

