\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0009_image_archive_index.sql
RESET ROLE;
