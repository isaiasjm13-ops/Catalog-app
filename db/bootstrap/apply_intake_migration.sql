\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0007_secure_intake.sql
RESET ROLE;
