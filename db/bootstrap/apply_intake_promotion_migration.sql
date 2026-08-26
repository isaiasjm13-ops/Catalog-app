\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0008_intake_promotion.sql
RESET ROLE;
