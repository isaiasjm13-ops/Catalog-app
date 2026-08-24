BEGIN;

-- Initial catalog review may only resolve pending identities and their exact
-- primary reference. Future reconciliation changes require a later migration.
CREATE FUNCTION perfect_catalog.guard_product_template_review()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
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

CREATE FUNCTION perfect_catalog.guard_product_variant_review()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW.product_variant_id, NEW.product_template_id, NEW.source_system_id,
        NEW.odoo_variant_id, NEW.odoo_external_id, NEW.variant_name,
        NEW.attributes, NEW.source_active, NEW.created_from_staging_row_id,
        NEW.created_at)
       IS DISTINCT FROM
       (OLD.product_variant_id, OLD.product_template_id, OLD.source_system_id,
        OLD.odoo_variant_id, OLD.odoo_external_id, OLD.variant_name,
        OLD.attributes, OLD.source_active, OLD.created_from_staging_row_id,
        OLD.created_at) THEN
        RAISE EXCEPTION 'product_variant review cannot change catalog data';
    END IF;
    IF OLD.catalog_status <> 'pending_review'
       OR NEW.catalog_status NOT IN ('active', 'inactive')
       OR NEW.updated_at IS NULL THEN
        RAISE EXCEPTION 'invalid product_variant review transition: % to %',
            OLD.catalog_status, NEW.catalog_status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION perfect_catalog.guard_product_reference_review()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW.product_reference_id, NEW.source_system_id, NEW.brand_id,
        NEW.product_template_id, NEW.product_variant_id, NEW.staging_row_id,
        NEW.reference_type, NEW.value_original, NEW.value_normalized,
        NEW.is_primary, NEW.confidence, NEW.created_at)
       IS DISTINCT FROM
       (OLD.product_reference_id, OLD.source_system_id, OLD.brand_id,
        OLD.product_template_id, OLD.product_variant_id, OLD.staging_row_id,
        OLD.reference_type, OLD.value_original, OLD.value_normalized,
        OLD.is_primary, OLD.confidence, OLD.created_at) THEN
        RAISE EXCEPTION 'product_reference review cannot change reference data';
    END IF;
    IF COALESCE(OLD.review_status, 'pending') <> 'pending'
       OR NEW.review_status NOT IN ('approved', 'rejected')
       OR NEW.reviewed_by IS NULL OR btrim(NEW.reviewed_by) = ''
       OR NEW.reviewed_at IS NULL OR NEW.review_note IS NULL
       OR btrim(NEW.review_note) = '' OR NEW.updated_at IS NULL THEN
        RAISE EXCEPTION 'invalid product_reference review transition: % to %',
            OLD.review_status, NEW.review_status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_product_template_review
BEFORE UPDATE ON perfect_catalog.product_template
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_product_template_review();

CREATE TRIGGER trg_product_variant_review
BEFORE UPDATE ON perfect_catalog.product_variant
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_product_variant_review();

CREATE TRIGGER trg_product_reference_review
BEFORE UPDATE ON perfect_catalog.product_reference
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_product_reference_review();

-- The supported decision is one atomic transaction: an active/inactive
-- identity and its primary reference must reach the matching final state.
CREATE FUNCTION perfect_catalog.validate_product_template_review_alignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_reference_status text;
    matching_references integer;
BEGIN
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

CREATE FUNCTION perfect_catalog.validate_product_variant_review_alignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_reference_status text;
    matching_references integer;
BEGIN
    expected_reference_status := CASE NEW.catalog_status
        WHEN 'active' THEN 'approved'
        WHEN 'inactive' THEN 'rejected'
    END;
    SELECT count(*) INTO matching_references
    FROM perfect_catalog.product_reference
    WHERE product_template_id=NEW.product_template_id
      AND product_variant_id=NEW.product_variant_id
      AND reference_type='internal' AND is_primary=true
      AND review_status=expected_reference_status;
    IF matching_references <> 1 THEN
        RAISE EXCEPTION 'product_variant review requires one aligned primary reference';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION perfect_catalog.validate_product_reference_review_alignment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    expected_catalog_status text;
    actual_catalog_status text;
BEGIN
    IF NEW.reference_type <> 'internal' OR NOT NEW.is_primary THEN
        RETURN NEW;
    END IF;
    expected_catalog_status := CASE NEW.review_status
        WHEN 'approved' THEN 'active'
        WHEN 'rejected' THEN 'inactive'
    END;
    IF NEW.product_variant_id IS NULL THEN
        SELECT catalog_status INTO actual_catalog_status
        FROM perfect_catalog.product_template
        WHERE product_template_id=NEW.product_template_id;
    ELSE
        SELECT catalog_status INTO actual_catalog_status
        FROM perfect_catalog.product_variant
        WHERE product_variant_id=NEW.product_variant_id
          AND product_template_id=NEW.product_template_id;
    END IF;
    IF actual_catalog_status IS DISTINCT FROM expected_catalog_status THEN
        RAISE EXCEPTION 'product_reference review is not aligned with its identity';
    END IF;
    RETURN NEW;
END;
$$;

CREATE CONSTRAINT TRIGGER trg_product_template_review_alignment
AFTER UPDATE ON perfect_catalog.product_template
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.validate_product_template_review_alignment();

CREATE CONSTRAINT TRIGGER trg_product_variant_review_alignment
AFTER UPDATE ON perfect_catalog.product_variant
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.validate_product_variant_review_alignment();

CREATE CONSTRAINT TRIGGER trg_product_reference_review_alignment
AFTER UPDATE ON perfect_catalog.product_reference
DEFERRABLE INITIALLY DEFERRED
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.validate_product_reference_review_alignment();

REVOKE UPDATE
ON perfect_catalog.product_template,
   perfect_catalog.product_variant,
   perfect_catalog.product_reference
FROM perfect_catalog_app;

GRANT UPDATE (catalog_status, updated_at)
ON perfect_catalog.product_template, perfect_catalog.product_variant
TO perfect_catalog_app;

GRANT UPDATE (review_status, reviewed_by, reviewed_at, review_note, updated_at)
ON perfect_catalog.product_reference
TO perfect_catalog_app;

COMMIT;
