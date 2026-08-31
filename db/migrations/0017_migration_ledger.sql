BEGIN;

CREATE TABLE perfect_catalog.schema_migration (
    migration_id text NOT NULL,
    checksum_sha256 char(64) NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    applied_by text NOT NULL,
    postgres_version text NOT NULL,
    execution_id uuid NOT NULL,
    notes text,
    CONSTRAINT pk_schema_migration PRIMARY KEY (migration_id),
    CONSTRAINT ck_schema_migration_id CHECK (migration_id ~ '^[0-9]{4}_[a-z0-9_]+$'),
    CONSTRAINT ck_schema_migration_checksum CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_schema_migration_actor CHECK (btrim(applied_by) <> ''),
    CONSTRAINT ck_schema_migration_version CHECK (btrim(postgres_version) <> '')
);

REVOKE ALL ON perfect_catalog.schema_migration FROM PUBLIC;
GRANT SELECT ON perfect_catalog.schema_migration TO perfect_catalog_readonly;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0017_migration_ledger', :'checksum_0017', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Ledger introducido después de verificar estructuralmente 0001-0016.'
);

COMMIT;
