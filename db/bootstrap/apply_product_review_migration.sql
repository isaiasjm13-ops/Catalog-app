\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0006_product_review_workflow.sql
RESET ROLE;
