BEGIN;

-- La migracion 0021 reclasifico NATSUKI como marca de Perfect. Decision del usuario del
-- 2026-09-04: NATSUKI vuelve a ser una Company propia. MASAKI y EXACTCARS quedan como
-- estaban (marcas de Perfect); esto no las toca. El Company legacy de NATSUKI
-- (ee7c7e0c-398f-5e35-9d79-c97d761f8672) nunca se borro -- 0021 lo desactivo por tener
-- referencias historicas -- asi que se reactiva en vez de crear un UUID nuevo.

DO $migration$
DECLARE
    v_natsuki_company uuid := 'ee7c7e0c-398f-5e35-9d79-c97d761f8672'::uuid;
    v_perfect_company uuid := '2ec779ba-2355-5151-babd-704cfa8f3ef0'::uuid;
    v_row record;
BEGIN
    SELECT * INTO v_row FROM perfect_catalog.company WHERE company_id=v_natsuki_company;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'No existe el Company legacy de NATSUKI; revisar antes de continuar.';
    END IF;

    IF NOT v_row.is_active THEN
        UPDATE perfect_catalog.company
        SET is_active=true, updated_at=CURRENT_TIMESTAMP
        WHERE company_id=v_natsuki_company;

        INSERT INTO perfect_catalog.company_admin_event (
            company_admin_event_id, company_id, action, code_snapshot,
            display_name_snapshot, actor, reason
        ) VALUES (
            gen_random_uuid(), v_natsuki_company, 'reactivated', v_row.code, v_row.display_name,
            current_user, 'Decision del usuario: NATSUKI vuelve a ser Company propia, no marca de Perfect.'
        );
    END IF;

    UPDATE perfect_catalog.brand
    SET company_id=v_natsuki_company
    WHERE code='NATSUKI' AND company_id=v_perfect_company;

    UPDATE perfect_catalog.brand_profile
    SET company_id=v_natsuki_company
    WHERE code='NATSUKI' AND company_id=v_perfect_company;

    -- Los planes de importacion existentes de NATSUKI deben seguir la Company de su
    -- Brand Profile, igual que hizo 0021 en la direccion opuesta.
    UPDATE perfect_catalog.import_plan AS p
    SET company_id=bp.company_id
    FROM perfect_catalog.brand_profile AS bp
    WHERE p.brand_profile_id=bp.brand_profile_id
      AND bp.code='NATSUKI'
      AND p.company_id IS DISTINCT FROM bp.company_id;

    -- MASAKI y EXACTCARS no se tocan: siguen siendo marcas de Perfect por decision
    -- explicita del usuario.
END
$migration$;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0025_natsuki_company_restored', :'checksum_0025', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'NATSUKI vuelve a ser Company propia (reactivada, no recreada); MASAKI y EXACTCARS quedan como marcas de Perfect.'
);

COMMIT;
