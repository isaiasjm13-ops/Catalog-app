\set ON_ERROR_STOP on

\echo 'Nueva contraseña para perfect_catalog_app (no se mostrará ni almacenará):'
\password perfect_catalog_app

SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole
FROM pg_roles
WHERE rolname = 'perfect_catalog_app';
