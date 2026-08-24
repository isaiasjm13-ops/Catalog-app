BEGIN;

-- Separate an already reconciled product from the stable UUID that a reviewed
-- plan will create or use later. Plans must persist before new product rows.
ALTER TABLE perfect_catalog.inventory_snapshot
    DROP CONSTRAINT fk_inventory_snapshot_exact_plan_item;

ALTER TABLE perfect_catalog.import_plan_item
    DROP CONSTRAINT uq_import_plan_item_snapshot_context,
    DROP CONSTRAINT ck_import_plan_item_variant_template,
    DROP CONSTRAINT ck_import_plan_item_inventory_product;

ALTER TABLE perfect_catalog.import_plan_item
    RENAME COLUMN product_template_id TO resolved_product_template_id;
ALTER TABLE perfect_catalog.import_plan_item
    RENAME COLUMN product_variant_id TO resolved_product_variant_id;
ALTER TABLE perfect_catalog.import_plan_item
    RENAME COLUMN product_target_id TO resolved_product_target_id;
ALTER TABLE perfect_catalog.import_plan_item
    RENAME COLUMN product_scope TO resolved_product_scope;

ALTER TABLE perfect_catalog.import_plan_item
    RENAME CONSTRAINT fk_import_plan_item_template TO fk_import_plan_item_resolved_template;
ALTER TABLE perfect_catalog.import_plan_item
    RENAME CONSTRAINT fk_import_plan_item_variant TO fk_import_plan_item_resolved_variant;
ALTER INDEX perfect_catalog.ix_import_plan_item_product
    RENAME TO ix_import_plan_item_resolved_product;

ALTER TABLE perfect_catalog.import_plan_item
    ADD COLUMN planned_product_template_id uuid NOT NULL,
    ADD COLUMN planned_product_variant_id uuid,
    ADD COLUMN planned_product_target_id uuid GENERATED ALWAYS AS (
        COALESCE(planned_product_variant_id, planned_product_template_id)
    ) STORED,
    ADD COLUMN planned_product_scope text GENERATED ALWAYS AS (
        CASE WHEN planned_product_variant_id IS NULL THEN 'template' ELSE 'variant' END
    ) STORED,
    ADD CONSTRAINT ck_import_plan_item_planned_variant_template CHECK (
        planned_product_variant_id IS NULL OR planned_product_template_id IS NOT NULL
    ),
    ADD CONSTRAINT ck_import_plan_item_resolved_variant_template CHECK (
        resolved_product_variant_id IS NULL OR resolved_product_template_id IS NOT NULL
    ),
    ADD CONSTRAINT ck_import_plan_item_resolved_matches_planned CHECK (
        resolved_product_template_id IS NULL
        OR (
            planned_product_template_id = resolved_product_template_id
            AND planned_product_variant_id IS NOT DISTINCT FROM resolved_product_variant_id
        )
    ),
    ADD CONSTRAINT ck_import_plan_item_create_is_unresolved CHECK (
        operation_type <> 'create' OR resolved_product_template_id IS NULL
    ),
    ADD CONSTRAINT ck_import_plan_item_existing_operation_resolved CHECK (
        operation_type NOT IN ('update', 'no_change') OR resolved_product_template_id IS NOT NULL
    ),
    ADD CONSTRAINT uq_import_plan_item_snapshot_context UNIQUE (
        import_plan_item_id,
        import_plan_id,
        import_file_id,
        staging_row_id,
        operation_type,
        planned_product_template_id,
        planned_product_scope,
        planned_product_target_id
    );

CREATE INDEX ix_import_plan_item_planned_product
    ON perfect_catalog.import_plan_item (
        planned_product_template_id,
        planned_product_variant_id
    );

-- A snapshot is written only during apply. At that point it must reference a
-- real product and match the exact future target reviewed in the plan item.
ALTER TABLE perfect_catalog.inventory_snapshot
    ADD CONSTRAINT fk_inventory_snapshot_template
    FOREIGN KEY (product_template_id)
    REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (
        product_template_id,
        product_variant_id
    ) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_exact_plan_item
    FOREIGN KEY (
        import_plan_item_id,
        import_plan_id,
        import_file_id,
        staging_row_id,
        plan_item_operation_type,
        product_template_id,
        product_scope,
        product_target_id
    )
    REFERENCES perfect_catalog.import_plan_item (
        import_plan_item_id,
        import_plan_id,
        import_file_id,
        staging_row_id,
        operation_type,
        planned_product_template_id,
        planned_product_scope,
        planned_product_target_id
    ) ON DELETE RESTRICT;

COMMIT;

