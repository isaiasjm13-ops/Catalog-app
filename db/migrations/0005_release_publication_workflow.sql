BEGIN;

-- Releases are complete, immutable snapshots. They are inserted as drafts and
-- only their lifecycle evidence may change afterwards.
CREATE FUNCTION perfect_catalog.guard_catalog_release_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.status <> 'draft'
       OR NEW.snapshot_sha256 IS NULL
       OR NEW.published_at IS NOT NULL
       OR NEW.published_by IS NOT NULL
       OR NEW.archived_at IS NOT NULL
       OR NEW.archived_by IS NOT NULL THEN
        RAISE EXCEPTION 'catalog_release must be inserted as a complete draft';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION perfect_catalog.guard_catalog_release_update()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF (NEW.catalog_release_id, NEW.brand_id, NEW.version, NEW.definition,
        NEW.created_at, NEW.created_by, NEW.notes, NEW.snapshot_sha256)
       IS DISTINCT FROM
       (OLD.catalog_release_id, OLD.brand_id, OLD.version, OLD.definition,
        OLD.created_at, OLD.created_by, OLD.notes, OLD.snapshot_sha256) THEN
        RAISE EXCEPTION 'catalog_release definition and checksum are immutable';
    END IF;

    IF OLD.status = 'draft' AND NEW.status = 'published' THEN
        IF OLD.published_at IS NOT NULL OR OLD.published_by IS NOT NULL
           OR NEW.published_at IS NULL OR NEW.published_by IS NULL
           OR NEW.archived_at IS NOT NULL OR NEW.archived_by IS NOT NULL THEN
            RAISE EXCEPTION 'invalid draft to published evidence';
        END IF;
    ELSIF OLD.status = 'published' AND NEW.status = 'archived' THEN
        IF NEW.published_at IS DISTINCT FROM OLD.published_at
           OR NEW.published_by IS DISTINCT FROM OLD.published_by
           OR OLD.archived_at IS NOT NULL OR OLD.archived_by IS NOT NULL
           OR NEW.archived_at IS NULL OR NEW.archived_by IS NULL THEN
            RAISE EXCEPTION 'invalid published to archived evidence';
        END IF;
    ELSE
        RAISE EXCEPTION 'invalid catalog_release transition: % to %', OLD.status, NEW.status;
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION perfect_catalog.guard_catalog_release_delete()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION 'catalog_release is append-only and cannot be deleted';
END;
$$;

CREATE FUNCTION perfect_catalog.guard_catalog_release_item_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    release_status text;
BEGIN
    SELECT status
    INTO release_status
    FROM perfect_catalog.catalog_release
    WHERE catalog_release_id = NEW.catalog_release_id
    FOR SHARE;

    IF release_status IS NULL THEN
        RAISE EXCEPTION 'catalog_release % does not exist', NEW.catalog_release_id;
    END IF;
    IF release_status <> 'draft' THEN
        RAISE EXCEPTION 'items can only be inserted into a draft release';
    END IF;
    RETURN NEW;
END;
$$;

CREATE FUNCTION perfect_catalog.guard_append_only_row()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    RAISE EXCEPTION '% is append-only', TG_TABLE_NAME;
END;
$$;

CREATE TRIGGER trg_catalog_release_insert
BEFORE INSERT ON perfect_catalog.catalog_release
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_catalog_release_insert();

CREATE TRIGGER trg_catalog_release_update
BEFORE UPDATE ON perfect_catalog.catalog_release
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_catalog_release_update();

CREATE TRIGGER trg_catalog_release_delete
BEFORE DELETE ON perfect_catalog.catalog_release
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_catalog_release_delete();

CREATE TRIGGER trg_catalog_release_item_insert
BEFORE INSERT ON perfect_catalog.catalog_release_item
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_catalog_release_item_insert();

CREATE TRIGGER trg_catalog_release_item_append_only
BEFORE UPDATE OR DELETE ON perfect_catalog.catalog_release_item
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

CREATE TRIGGER trg_audit_event_append_only
BEFORE UPDATE OR DELETE ON perfect_catalog.audit_event
FOR EACH ROW EXECUTE FUNCTION perfect_catalog.guard_append_only_row();

CREATE UNIQUE INDEX uq_catalog_release_item_public_identity
    ON perfect_catalog.catalog_release_item (
        catalog_release_id,
        COALESCE(product_variant_id, product_template_id)
    );

REVOKE INSERT, UPDATE, DELETE
ON perfect_catalog.catalog_release, perfect_catalog.catalog_release_item
FROM perfect_catalog_app;

GRANT INSERT
ON perfect_catalog.catalog_release, perfect_catalog.catalog_release_item
TO perfect_catalog_app;

GRANT UPDATE (status, published_at, published_by, archived_at, archived_by)
ON perfect_catalog.catalog_release
TO perfect_catalog_app;

COMMIT;
