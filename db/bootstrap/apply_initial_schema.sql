\set ON_ERROR_STOP on

SELECT count(*)::int AS existing_schema_count
FROM pg_namespace
WHERE nspname = 'perfect_catalog'
\gset

\if :existing_schema_count
    \echo 'ERROR: schema perfect_catalog already exists; migration stopped.'
    \quit 3
\endif

SET ROLE perfect_catalog_owner;
\ir ../migrations/0001_initial_schema.sql

REVOKE ALL ON SCHEMA perfect_catalog FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA perfect_catalog FROM PUBLIC;

GRANT USAGE ON SCHEMA perfect_catalog TO perfect_catalog_app, perfect_catalog_readonly;
GRANT SELECT ON ALL TABLES IN SCHEMA perfect_catalog TO perfect_catalog_app, perfect_catalog_readonly;

GRANT INSERT, UPDATE ON
    perfect_catalog.source_system,
    perfect_catalog.import_batch
TO perfect_catalog_app;

GRANT INSERT ON
    perfect_catalog.import_file,
    perfect_catalog.staging_row,
    perfect_catalog.staging_row_result,
    perfect_catalog.import_issue,
    perfect_catalog.import_plan,
    perfect_catalog.import_plan_item
TO perfect_catalog_app;

ALTER DEFAULT PRIVILEGES FOR ROLE perfect_catalog_owner IN SCHEMA perfect_catalog
    REVOKE ALL ON TABLES FROM PUBLIC;
ALTER DEFAULT PRIVILEGES FOR ROLE perfect_catalog_owner IN SCHEMA perfect_catalog
    GRANT SELECT ON TABLES TO perfect_catalog_readonly;

RESET ROLE;

