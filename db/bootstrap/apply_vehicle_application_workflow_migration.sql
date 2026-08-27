\set ON_ERROR_STOP on
SET ROLE perfect_catalog_owner;
\ir ../migrations/0012_vehicle_application_workflow.sql
RESET ROLE;
