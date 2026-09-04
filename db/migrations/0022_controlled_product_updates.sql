BEGIN;

-- Controlled source updates reuse the reviewed import_plan as the change request.
-- Direct UPDATE on product_template remains unavailable to perfect_catalog_app.
CREATE OR REPLACE FUNCTION perfect_catalog.guard_product_template_review()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- A controlled import update runs inside a SECURITY DEFINER function owned by
    -- perfect_catalog_owner and marks only that transaction-local call. The app
    -- role cannot satisfy both conditions by setting the custom GUC itself.
    IF current_user = 'perfect_catalog_owner'
       AND current_setting('perfect_catalog.controlled_product_update', true) = 'on' THEN
        IF (NEW.product_template_id, NEW.source_system_id, NEW.brand_id,
            NEW.odoo_template_id, NEW.odoo_external_id, NEW.currency_code,
            NEW.uom_original, NEW.activity_state, NEW.is_favorite,
            NEW.show_quantity_status, NEW.source_active, NEW.source_updated_at,
            NEW.created_from_staging_row_id, NEW.created_at, NEW.catalog_status)
           IS DISTINCT FROM
           (OLD.product_template_id, OLD.source_system_id, OLD.brand_id,
            OLD.odoo_template_id, OLD.odoo_external_id, OLD.currency_code,
            OLD.uom_original, OLD.activity_state, OLD.is_favorite,
            OLD.show_quantity_status, OLD.source_active, OLD.source_updated_at,
            OLD.created_from_staging_row_id, OLD.created_at, OLD.catalog_status) THEN
            RAISE EXCEPTION 'controlled product update attempted to change protected identity/local fields';
        END IF;
        IF NEW.updated_at IS NULL THEN
            RAISE EXCEPTION 'controlled product update requires updated_at';
        END IF;
        RETURN NEW;
    END IF;

    IF (NEW.product_template_id, NEW.source_system_id, NEW.brand_id,
        NEW.product_category_id, NEW.odoo_template_id, NEW.odoo_external_id,
        NEW.name_original, NEW.name_normalized, NEW.currency_code,
        NEW.uom_original, NEW.activity_state, NEW.is_favorite,
        NEW.show_quantity_status, NEW.source_active, NEW.variant_count_observed,
        NEW.source_updated_at, NEW.created_from_staging_row_id,
        NEW.last_confirmed_batch_id, NEW.created_at)
       IS DISTINCT FROM
       (OLD.product_template_id, OLD.source_system_id, OLD.brand_id,
        OLD.product_category_id, OLD.odoo_template_id, OLD.odoo_external_id,
        OLD.name_original, OLD.name_normalized, OLD.currency_code,
        OLD.uom_original, OLD.activity_state, OLD.is_favorite,
        OLD.show_quantity_status, OLD.source_active, OLD.variant_count_observed,
        OLD.source_updated_at, OLD.created_from_staging_row_id,
        OLD.last_confirmed_batch_id, OLD.created_at) THEN
        RAISE EXCEPTION 'product_template review cannot change catalog data';
    END IF;
    IF OLD.catalog_status <> 'pending_review'
       OR NEW.catalog_status NOT IN ('active', 'inactive')
       OR NEW.updated_at IS NULL THEN
        RAISE EXCEPTION 'invalid product_template review transition: % to %',
            OLD.catalog_status, NEW.catalog_status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION perfect_catalog.validate_product_template_review_alignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_reference_status text;
    matching_references integer;
BEGIN
    -- Controlled source updates preserve catalog_status. Alignment is only a
    -- review invariant when the review state itself changes.
    IF OLD.catalog_status IS NOT DISTINCT FROM NEW.catalog_status THEN
        RETURN NEW;
    END IF;
    expected_reference_status := CASE NEW.catalog_status
        WHEN 'active' THEN 'approved'
        WHEN 'inactive' THEN 'rejected'
    END;
    SELECT count(*) INTO matching_references
    FROM perfect_catalog.product_reference
    WHERE product_template_id=NEW.product_template_id
      AND product_variant_id IS NULL
      AND reference_type='internal' AND is_primary=true
      AND review_status=expected_reference_status;
    IF matching_references <> 1 THEN
        RAISE EXCEPTION 'product_template review requires one aligned primary reference';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION perfect_catalog.apply_controlled_product_update(
    p_import_plan_id uuid,
    p_import_plan_item_id uuid,
    p_expected_fingerprint text
)
RETURNS jsonb
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, perfect_catalog
AS $$
DECLARE
    v_plan record;
    v_item record;
    v_product record;
    v_before_variant integer;
    v_incoming_variant integer;
    v_new_name text;
    v_new_normalized text;
    v_new_category_path text;
    v_new_category_id uuid;
    v_new_variant integer;
    v_before jsonb;
    v_after jsonb;
BEGIN
    IF p_import_plan_id IS NULL OR p_import_plan_item_id IS NULL THEN
        RAISE EXCEPTION 'controlled update requires plan and item ids';
    END IF;
    IF p_expected_fingerprint IS NULL
       OR p_expected_fingerprint !~ '^[0-9a-f]{64}$' THEN
        RAISE EXCEPTION 'controlled update requires a valid fingerprint';
    END IF;

    SELECT p.import_plan_id, p.import_batch_id, p.company_id, p.brand_profile_id,
           p.plan_status, p.approved_at, p.approved_by,
           p.approval_fingerprint_sha256, b.source_system_id
    INTO v_plan
    FROM perfect_catalog.import_plan AS p
    JOIN perfect_catalog.import_batch AS b ON b.import_batch_id=p.import_batch_id
    WHERE p.import_plan_id=p_import_plan_id
    FOR UPDATE OF p;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'controlled update plan does not exist';
    END IF;
    IF v_plan.plan_status <> 'applying'
       OR v_plan.approved_at IS NULL OR v_plan.approved_by IS NULL THEN
        RAISE EXCEPTION 'controlled update requires an approved plan in applying state';
    END IF;
    IF v_plan.approval_fingerprint_sha256 <> p_expected_fingerprint THEN
        RAISE EXCEPTION 'controlled update fingerprint mismatch';
    END IF;
    IF v_plan.company_id IS NULL OR v_plan.brand_profile_id IS NULL THEN
        RAISE EXCEPTION 'controlled update requires Company and Brand context';
    END IF;

    SELECT i.import_plan_item_id, i.import_plan_id, i.staging_row_id,
           i.resolved_product_template_id, i.planned_product_template_id,
           i.operation_type, i.before_values, i.proposed_values
    INTO v_item
    FROM perfect_catalog.import_plan_item AS i
    WHERE i.import_plan_item_id=p_import_plan_item_id
      AND i.import_plan_id=p_import_plan_id
    FOR UPDATE OF i;

    IF NOT FOUND OR v_item.operation_type <> 'update'
       OR v_item.resolved_product_template_id IS NULL
       OR v_item.planned_product_template_id IS DISTINCT FROM v_item.resolved_product_template_id THEN
        RAISE EXCEPTION 'controlled update item is not a valid UPDATE target';
    END IF;

    SELECT pt.product_template_id, pt.source_system_id, pt.brand_id,
           pt.product_category_id, pc.source_path AS category_path,
           pt.name_original, pt.name_normalized, pt.variant_count_observed,
           pt.last_confirmed_batch_id, pt.catalog_status,
           br.brand_profile_id, br.company_id, br.is_active AS brand_is_active,
           co.is_active AS company_is_active
    INTO v_product
    FROM perfect_catalog.product_template AS pt
    JOIN perfect_catalog.brand AS br ON br.brand_id=pt.brand_id
    JOIN perfect_catalog.company AS co ON co.company_id=br.company_id
    LEFT JOIN perfect_catalog.product_category AS pc
      ON pc.product_category_id=pt.product_category_id
    WHERE pt.product_template_id=v_item.resolved_product_template_id
    FOR UPDATE OF pt;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'controlled update product does not exist';
    END IF;
    IF v_product.source_system_id <> v_plan.source_system_id
       OR v_product.company_id <> v_plan.company_id
       OR v_product.brand_profile_id IS DISTINCT FROM v_plan.brand_profile_id
       OR NOT v_product.company_is_active OR NOT v_product.brand_is_active THEN
        RAISE EXCEPTION 'controlled update Company/Brand/source context changed after approval';
    END IF;

    IF NOT (v_item.before_values ? 'name_original')
       OR NOT (v_item.before_values ? 'name_normalized')
       OR NOT (v_item.before_values ? 'category_path')
       OR NOT (v_item.before_values ? 'variant_count_observed') THEN
        RAISE EXCEPTION 'controlled update before_values are incomplete';
    END IF;

    IF jsonb_typeof(v_item.before_values->'variant_count_observed') = 'null' THEN
        v_before_variant := NULL;
    ELSE
        v_before_variant := (v_item.before_values->>'variant_count_observed')::integer;
    END IF;

    IF v_product.name_original IS DISTINCT FROM (v_item.before_values->>'name_original')
       OR v_product.name_normalized IS DISTINCT FROM (v_item.before_values->>'name_normalized')
       OR v_product.category_path IS DISTINCT FROM (v_item.before_values->>'category_path')
       OR v_product.variant_count_observed IS DISTINCT FROM v_before_variant THEN
        RAISE EXCEPTION 'controlled update conflict: product changed after plan approval';
    END IF;

    v_new_name := NULLIF(btrim(v_item.proposed_values->>'name_original'), '');
    IF v_new_name IS NULL THEN
        v_new_name := v_product.name_original;
        v_new_normalized := v_product.name_normalized;
    ELSE
        v_new_normalized := NULLIF(btrim(v_item.proposed_values->>'name_normalized'), '');
        IF v_new_normalized IS NULL THEN
            RAISE EXCEPTION 'controlled update requires normalized name with a new name';
        END IF;
    END IF;

    v_new_category_path := NULLIF(btrim(v_item.proposed_values->>'category_path'), '');
    IF v_new_category_path IS NULL OR v_new_category_path IS NOT DISTINCT FROM v_product.category_path THEN
        v_new_category_id := v_product.product_category_id;
    ELSE
        SELECT pc.product_category_id INTO v_new_category_id
        FROM perfect_catalog.product_category AS pc
        WHERE pc.source_system_id=v_plan.source_system_id
          AND pc.source_path=v_new_category_path
        ORDER BY pc.product_category_id
        LIMIT 1;
        IF v_new_category_id IS NULL THEN
            RAISE EXCEPTION 'controlled update category has not been materialized';
        END IF;
    END IF;

    IF v_item.proposed_values->'variant_count_observed' IS NULL
       OR jsonb_typeof(v_item.proposed_values->'variant_count_observed') = 'null'
       OR btrim(v_item.proposed_values->>'variant_count_observed') = '' THEN
        v_new_variant := v_product.variant_count_observed;
    ELSE
        v_incoming_variant := (v_item.proposed_values->>'variant_count_observed')::integer;
        IF v_incoming_variant < 0 THEN
            RAISE EXCEPTION 'controlled update variant_count_observed cannot be negative';
        END IF;
        v_new_variant := v_incoming_variant;
    END IF;

    IF (v_new_name, v_new_normalized, v_new_category_id, v_new_variant)
       IS NOT DISTINCT FROM
       (v_product.name_original, v_product.name_normalized,
        v_product.product_category_id, v_product.variant_count_observed) THEN
        RAISE EXCEPTION 'controlled UPDATE has no effective source-managed changes';
    END IF;

    v_before := jsonb_build_object(
        'name_original', v_product.name_original,
        'name_normalized', v_product.name_normalized,
        'category_path', v_product.category_path,
        'variant_count_observed', v_product.variant_count_observed,
        'last_confirmed_batch_id', v_product.last_confirmed_batch_id,
        'catalog_status', v_product.catalog_status
    );

    PERFORM set_config('perfect_catalog.controlled_product_update', 'on', true);
    UPDATE perfect_catalog.product_template
    SET product_category_id=v_new_category_id,
        name_original=v_new_name,
        name_normalized=v_new_normalized,
        variant_count_observed=v_new_variant,
        last_confirmed_batch_id=v_plan.import_batch_id,
        updated_at=CURRENT_TIMESTAMP
    WHERE product_template_id=v_product.product_template_id;
    PERFORM set_config('perfect_catalog.controlled_product_update', 'off', true);

    SELECT jsonb_build_object(
        'name_original', pt.name_original,
        'name_normalized', pt.name_normalized,
        'category_path', pc.source_path,
        'variant_count_observed', pt.variant_count_observed,
        'last_confirmed_batch_id', pt.last_confirmed_batch_id,
        'catalog_status', pt.catalog_status
    )
    INTO v_after
    FROM perfect_catalog.product_template AS pt
    LEFT JOIN perfect_catalog.product_category AS pc
      ON pc.product_category_id=pt.product_category_id
    WHERE pt.product_template_id=v_product.product_template_id;

    RETURN jsonb_build_object(
        'product_template_id', v_product.product_template_id,
        'before', v_before,
        'after', v_after
    );
END;
$$;

REVOKE ALL ON FUNCTION perfect_catalog.apply_controlled_product_update(uuid, uuid, text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION perfect_catalog.apply_controlled_product_update(uuid, uuid, text)
TO perfect_catalog_app;

-- Keep direct table updates tightly scoped to the original review workflow.
REVOKE UPDATE ON perfect_catalog.product_template FROM perfect_catalog_app;
GRANT UPDATE (catalog_status, updated_at)
ON perfect_catalog.product_template TO perfect_catalog_app;

INSERT INTO perfect_catalog.schema_migration (
    migration_id, checksum_sha256, applied_by, postgres_version, execution_id, notes
) VALUES (
    '0022_controlled_product_updates', :'checksum_0022', current_user,
    current_setting('server_version'), gen_random_uuid(),
    'UPDATE controlado de datos source-managed mediante import_plan aprobado; UPDATE directo permanece bloqueado.'
);

COMMIT;
