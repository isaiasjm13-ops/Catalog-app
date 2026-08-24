\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0003_apply_workflow_permissions.sql
RESET ROLE;
