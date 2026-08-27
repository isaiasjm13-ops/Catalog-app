BEGIN;

ALTER TABLE perfect_catalog.brand_profile
    ADD COLUMN title_font_family text NOT NULL DEFAULT 'Barlow Condensed',
    ADD COLUMN body_font_family text NOT NULL DEFAULT 'DM Sans',
    ADD COLUMN minimum_font_size_pt numeric(5,2) NOT NULL DEFAULT 12.00,
    ADD COLUMN body_line_height numeric(4,2) NOT NULL DEFAULT 1.80,
    ADD COLUMN logo_asset_key text,
    ADD COLUMN corner_logo_enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN watermark_enabled boolean NOT NULL DEFAULT true,
    ADD COLUMN watermark_opacity numeric(4,3) NOT NULL DEFAULT 0.050,
    ADD CONSTRAINT ck_brand_profile_title_font CHECK (btrim(title_font_family) <> ''),
    ADD CONSTRAINT ck_brand_profile_body_font CHECK (btrim(body_font_family) <> ''),
    ADD CONSTRAINT ck_brand_profile_minimum_font CHECK (minimum_font_size_pt >= 12),
    ADD CONSTRAINT ck_brand_profile_line_height CHECK (body_line_height >= 1 AND body_line_height <= 3),
    ADD CONSTRAINT ck_brand_profile_logo_key CHECK (logo_asset_key IS NULL OR logo_asset_key ~ '^[a-z0-9][a-z0-9/_-]*[.]svg$'),
    ADD CONSTRAINT ck_brand_profile_watermark CHECK (watermark_opacity BETWEEN 0.04 AND 0.07);

UPDATE perfect_catalog.brand_profile
SET logo_asset_key='brands/natsuki/logo.svg'
WHERE code='NATSUKI';

ALTER TABLE perfect_catalog.import_plan ADD COLUMN brand_profile_id uuid;
ALTER TABLE perfect_catalog.brand ADD COLUMN brand_profile_id uuid;

ALTER TABLE perfect_catalog.import_plan
    ADD CONSTRAINT fk_import_plan_brand_profile
    FOREIGN KEY (brand_profile_id) REFERENCES perfect_catalog.brand_profile (brand_profile_id) ON DELETE RESTRICT;
ALTER TABLE perfect_catalog.brand
    ADD CONSTRAINT fk_brand_profile
    FOREIGN KEY (brand_profile_id) REFERENCES perfect_catalog.brand_profile (brand_profile_id) ON DELETE RESTRICT;

UPDATE perfect_catalog.brand AS b
SET brand_profile_id=p.brand_profile_id
FROM perfect_catalog.brand_profile AS p
WHERE p.code='NATSUKI' AND upper(b.code)=p.code;

GRANT UPDATE (brand_profile_id) ON perfect_catalog.import_plan TO perfect_catalog_app;

COMMIT;
