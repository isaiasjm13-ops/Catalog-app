BEGIN;

-- Seleccion manual de fotos: cuando una foto quedo ambigua o sin coincidencia exacta, el operador
-- puede elegir a que producto pertenece. Sigue siendo evidencia append-only: se crea un candidato
-- con el algoritmo 'operator-selected-v1' y su decision humana en la misma transaccion. Los
-- algoritmos anteriores se conservan porque ya hay candidatos reales generados con ellos.

ALTER TABLE perfect_catalog.image_product_candidate
    DROP CONSTRAINT IF EXISTS ck_image_product_candidate_algorithm;

ALTER TABLE perfect_catalog.image_product_candidate
    ADD CONSTRAINT ck_image_product_candidate_algorithm
    CHECK (algorithm IN (
        'exact-approved-reference-v1',
        'exact-approved-reference-v2',
        'exact-approved-reference-v3',
        'operator-selected-v1'
    ));

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0029_manual_image_selection', :'checksum_0029', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'Permite candidatos de imagen elegidos por el operador (algoritmo operator-selected-v1).'
);

COMMIT;
