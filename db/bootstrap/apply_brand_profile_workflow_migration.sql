\set ON_ERROR_STOP on
SET ROLE perfect_catalog_owner;
\ir ../migrations/0014_brand_profile_workflow.sql
RESET ROLE;
