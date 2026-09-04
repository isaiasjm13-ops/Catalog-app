BEGIN;

-- El sufijo numerico (-2, -3...) no cubria la convencion real de nombres del catalogo: letras
-- por cada foto, incluida la primera (REF-1234 A, REF-1234 - B, REF-1234 (C), etc.). El
-- algoritmo v3 reconoce ambas convenciones; v1 y v2 se conservan porque ya hay candidatos
-- reales generados con esas versiones y son evidencia append-only, nunca se reescriben.

ALTER TABLE perfect_catalog.image_product_candidate
    DROP CONSTRAINT IF EXISTS ck_image_product_candidate_algorithm;

ALTER TABLE perfect_catalog.image_product_candidate
    ADD CONSTRAINT ck_image_product_candidate_algorithm
    CHECK (algorithm IN (
        'exact-approved-reference-v1',
        'exact-approved-reference-v2',
        'exact-approved-reference-v3'
    ));

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0027_image_variant_letter_suffix', :'checksum_0027', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Reconoce sufijo de una sola letra (A, B, C...) para fotos variantes, ademas del numerico.'
);

COMMIT;
