\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0004_restore_application_reads.sql
RESET ROLE;
