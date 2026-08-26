\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0010_image_match_review.sql
RESET ROLE;
