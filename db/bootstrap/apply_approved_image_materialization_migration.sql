\set ON_ERROR_STOP on
SET ROLE perfect_catalog_owner;
\ir ../migrations/0011_approved_image_materialization.sql
RESET ROLE;
