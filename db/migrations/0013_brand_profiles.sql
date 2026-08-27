BEGIN;

CREATE TABLE perfect_catalog.brand_profile (
    brand_profile_id uuid NOT NULL,
    code text NOT NULL,
    display_name text NOT NULL,
    tagline text,
    primary_color char(7) NOT NULL,
    secondary_color char(7) NOT NULL,
    ink_color char(7) NOT NULL,
    paper_color char(7) NOT NULL,
    public_base_url text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by text NOT NULL,
    creation_reason text NOT NULL,
    CONSTRAINT pk_brand_profile PRIMARY KEY (brand_profile_id),
    CONSTRAINT uq_brand_profile_code UNIQUE (code),
    CONSTRAINT ck_brand_profile_code CHECK (code ~ '^[A-Z0-9][A-Z0-9_-]{1,31}$'),
    CONSTRAINT ck_brand_profile_name CHECK (btrim(display_name) <> ''),
    CONSTRAINT ck_brand_profile_tagline CHECK (tagline IS NULL OR btrim(tagline) <> ''),
    CONSTRAINT ck_brand_profile_primary CHECK (primary_color ~ '^#[0-9A-F]{6}$'),
    CONSTRAINT ck_brand_profile_secondary CHECK (secondary_color ~ '^#[0-9A-F]{6}$'),
    CONSTRAINT ck_brand_profile_ink CHECK (ink_color ~ '^#[0-9A-F]{6}$'),
    CONSTRAINT ck_brand_profile_paper CHECK (paper_color ~ '^#[0-9A-F]{6}$'),
    CONSTRAINT ck_brand_profile_url CHECK (public_base_url IS NULL OR public_base_url ~ '^https://[^[:space:]]+$'),
    CONSTRAINT ck_brand_profile_actor CHECK (btrim(created_by) <> ''),
    CONSTRAINT ck_brand_profile_reason CHECK (length(btrim(creation_reason)) BETWEEN 4 AND 500)
);

INSERT INTO perfect_catalog.brand_profile (
    brand_profile_id, code, display_name, tagline,
    primary_color, secondary_color, ink_color, paper_color,
    created_by, creation_reason
) VALUES (
    '9ed94760-1423-5e1f-a026-48e744de2ccd', 'NATSUKI', 'Natsuki',
    'Trust the best, trust Natsuki', '#C60012', '#202327', '#16191D', '#FFFFFF',
    'migration-0013', 'Perfil inicial compatible con los catalogos existentes'
) ON CONFLICT (code) DO NOTHING;

REVOKE ALL ON perfect_catalog.brand_profile FROM PUBLIC;
GRANT SELECT, INSERT ON perfect_catalog.brand_profile TO perfect_catalog_app;
GRANT SELECT ON perfect_catalog.brand_profile TO perfect_catalog_readonly;

COMMIT;
