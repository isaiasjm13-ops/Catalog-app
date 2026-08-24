\set ON_ERROR_STOP on

-- This bootstrap intentionally fails if any target role or database already exists.
SELECT (
    EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'perfect_catalog_owner')
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'perfect_catalog_app')
    OR EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'perfect_catalog_readonly')
    OR EXISTS (SELECT 1 FROM pg_database WHERE datname = 'perfect_catalog_dev')
)::int AS target_exists \gset

\if :target_exists
    \echo 'ERROR: a target role or perfect_catalog_dev already exists; bootstrap stopped.'
    \quit 3
\endif

CREATE ROLE perfect_catalog_owner
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

CREATE ROLE perfect_catalog_app
    LOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

\echo 'Enter a new password for perfect_catalog_app. It will not be echoed or stored by this script.'
\password perfect_catalog_app

CREATE ROLE perfect_catalog_readonly
    NOLOGIN
    NOSUPERUSER
    NOCREATEDB
    NOCREATEROLE
    NOINHERIT
    NOREPLICATION
    NOBYPASSRLS;

CREATE DATABASE perfect_catalog_dev
    WITH OWNER = perfect_catalog_owner
         TEMPLATE = template0
         ENCODING = 'UTF8'
         LOCALE_PROVIDER = icu
         ICU_LOCALE = 'es-PA';

REVOKE ALL ON DATABASE perfect_catalog_dev FROM PUBLIC;
GRANT CONNECT ON DATABASE perfect_catalog_dev TO perfect_catalog_app, perfect_catalog_readonly;
ALTER DATABASE perfect_catalog_dev SET timezone TO 'UTC';

\connect perfect_catalog_dev postgres localhost 5432

REVOKE ALL ON SCHEMA public FROM PUBLIC;

SELECT
    d.datname,
    pg_get_userbyid(d.datdba) AS owner,
    pg_encoding_to_char(d.encoding) AS encoding,
    d.datlocprovider,
    d.datlocale,
    d.datcollversion,
    current_setting('TimeZone') AS timezone,
    has_database_privilege('perfect_catalog_app', d.datname, 'CONNECT') AS app_can_connect,
    has_database_privilege('perfect_catalog_readonly', d.datname, 'CONNECT') AS readonly_can_connect,
    has_database_privilege('public', d.datname, 'CONNECT') AS public_can_connect
FROM pg_database AS d
WHERE d.datname = 'perfect_catalog_dev';

