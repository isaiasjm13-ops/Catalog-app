\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0005_release_publication_workflow.sql
RESET ROLE;
