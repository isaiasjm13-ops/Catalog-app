\set ON_ERROR_STOP on
SET ROLE perfect_catalog_owner;
\ir ../migrations/0013_brand_profiles.sql
RESET ROLE;
