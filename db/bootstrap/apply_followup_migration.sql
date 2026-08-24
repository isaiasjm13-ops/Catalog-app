\set ON_ERROR_STOP on

SET ROLE perfect_catalog_owner;
\ir ../migrations/0002_plan_future_product_targets.sql
RESET ROLE;
