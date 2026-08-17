BEGIN;

-- Perfect Catalog PostgreSQL 16+ initial schema draft.
-- UUID values are supplied by the application.
CREATE SCHEMA perfect_catalog;

-- Integration and immutable evidence.
CREATE TABLE perfect_catalog.source_system (
    source_system_id uuid NOT NULL,
    code text NOT NULL,
    name text NOT NULL,
    system_type text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    base_url text,
    instance_key text,
    timezone_name text,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_source_system PRIMARY KEY (source_system_id),
    CONSTRAINT uq_source_system_code UNIQUE (code),
    CONSTRAINT ck_source_system_code_nonempty CHECK (btrim(code) <> ''),
    CONSTRAINT ck_source_system_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_source_system_type_nonempty CHECK (btrim(system_type) <> ''),
    CONSTRAINT ck_source_system_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.import_batch (
    import_batch_id uuid NOT NULL,
    source_system_id uuid NOT NULL,
    mode text NOT NULL,
    status text NOT NULL,
    scope jsonb NOT NULL,
    started_at timestamptz NOT NULL,
    finished_at timestamptz,
    requested_by text,
    approved_by text,
    profiler_version text,
    rules_version text,
    statistics jsonb,
    error_summary text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_import_batch PRIMARY KEY (import_batch_id),
    CONSTRAINT ck_import_batch_mode CHECK (mode IN ('dry_run', 'apply')),
    CONSTRAINT ck_import_batch_status CHECK (status IN (
        'received', 'hashing', 'duplicate_detected', 'registered', 'staging',
        'validating', 'normalizing', 'reconciling', 'planning', 'awaiting_review',
        'ready', 'dry_run_complete', 'applying', 'completed',
        'completed_with_warnings', 'blocked', 'rolled_back', 'failed', 'cancelled'
    )),
    CONSTRAINT ck_import_batch_finished_at CHECK (finished_at IS NULL OR finished_at >= started_at)
);

CREATE TABLE perfect_catalog.import_file (
    import_file_id uuid NOT NULL,
    import_batch_id uuid NOT NULL,
    original_name text NOT NULL,
    storage_uri text NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 char(64) NOT NULL,
    media_type text NOT NULL,
    received_at timestamptz NOT NULL,
    sheet_count integer,
    workbook_metadata jsonb,
    duplicate_of_file_id uuid,
    CONSTRAINT pk_import_file PRIMARY KEY (import_file_id),
    CONSTRAINT uq_import_file_batch_file UNIQUE (import_batch_id, import_file_id),
    CONSTRAINT ck_import_file_original_name_nonempty CHECK (btrim(original_name) <> ''),
    CONSTRAINT ck_import_file_storage_uri_nonempty CHECK (btrim(storage_uri) <> ''),
    CONSTRAINT ck_import_file_media_type_nonempty CHECK (btrim(media_type) <> ''),
    CONSTRAINT ck_import_file_size CHECK (size_bytes >= 0),
    CONSTRAINT ck_import_file_sheet_count CHECK (sheet_count IS NULL OR sheet_count >= 0),
    CONSTRAINT ck_import_file_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_file_not_self_duplicate CHECK (duplicate_of_file_id IS NULL OR duplicate_of_file_id <> import_file_id)
);

CREATE TABLE perfect_catalog.staging_row (
    staging_row_id uuid NOT NULL,
    import_file_id uuid NOT NULL,
    sheet_name text NOT NULL,
    source_row_number integer NOT NULL,
    raw_headers jsonb NOT NULL,
    raw_values jsonb NOT NULL,
    raw_excel_serials jsonb NOT NULL,
    structural_metadata jsonb NOT NULL,
    row_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_staging_row PRIMARY KEY (staging_row_id),
    CONSTRAINT uq_staging_row_source UNIQUE (import_file_id, sheet_name, source_row_number),
    CONSTRAINT ck_staging_row_sheet_nonempty CHECK (btrim(sheet_name) <> ''),
    CONSTRAINT ck_staging_row_number CHECK (source_row_number >= 1),
    CONSTRAINT ck_staging_row_sha256 CHECK (row_sha256 ~ '^[0-9a-f]{64}$')
);

CREATE TABLE perfect_catalog.staging_row_result (
    staging_row_result_id uuid NOT NULL,
    staging_row_id uuid NOT NULL,
    import_batch_id uuid NOT NULL,
    contract_version text NOT NULL,
    rules_version text NOT NULL,
    processing_stage text NOT NULL,
    attempt_number integer NOT NULL,
    status text NOT NULL,
    normalized_data jsonb NOT NULL,
    result_sha256 char(64) NOT NULL,
    processor_version text,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at timestamptz NOT NULL,
    CONSTRAINT pk_staging_row_result PRIMARY KEY (staging_row_result_id),
    CONSTRAINT uq_staging_row_result_version UNIQUE (
        staging_row_id,
        import_batch_id,
        contract_version,
        rules_version,
        processing_stage,
        attempt_number
    ),
    CONSTRAINT ck_staging_row_result_contract_nonempty CHECK (btrim(contract_version) <> ''),
    CONSTRAINT ck_staging_row_result_rules_nonempty CHECK (btrim(rules_version) <> ''),
    CONSTRAINT ck_staging_row_result_stage_nonempty CHECK (btrim(processing_stage) <> ''),
    CONSTRAINT ck_staging_row_result_status_nonempty CHECK (btrim(status) <> ''),
    CONSTRAINT ck_staging_row_result_attempt CHECK (attempt_number >= 1),
    CONSTRAINT ck_staging_row_result_sha256 CHECK (result_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_staging_row_result_completed_at CHECK (completed_at >= created_at)
);

CREATE TABLE perfect_catalog.import_issue (
    import_issue_id uuid NOT NULL,
    import_batch_id uuid NOT NULL,
    import_file_id uuid,
    staging_row_id uuid,
    staging_row_result_id uuid,
    severity text NOT NULL,
    code text NOT NULL,
    message text NOT NULL,
    status text NOT NULL,
    column_name text,
    details jsonb,
    resolved_at timestamptz,
    resolved_by text,
    resolution_note text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_import_issue PRIMARY KEY (import_issue_id),
    CONSTRAINT ck_import_issue_severity CHECK (severity IN ('info', 'warning', 'error', 'fatal')),
    CONSTRAINT ck_import_issue_status CHECK (status IN ('open', 'resolved', 'accepted')),
    CONSTRAINT ck_import_issue_code_nonempty CHECK (btrim(code) <> ''),
    CONSTRAINT ck_import_issue_message_nonempty CHECK (btrim(message) <> ''),
    CONSTRAINT ck_import_issue_resolution_pair CHECK (
        (resolved_at IS NULL AND resolved_by IS NULL)
        OR (resolved_at IS NOT NULL AND resolved_by IS NOT NULL)
    ),
    CONSTRAINT ck_import_issue_resolved_at CHECK (resolved_at IS NULL OR resolved_at >= created_at)
);

CREATE TABLE perfect_catalog.import_plan (
    import_plan_id uuid NOT NULL,
    import_batch_id uuid NOT NULL,
    import_file_id uuid NOT NULL,
    file_sha256 char(64) NOT NULL,
    contract_version text NOT NULL,
    rules_version text NOT NULL,
    plan_status text NOT NULL,
    plan_sha256 char(64) NOT NULL,
    approval_fingerprint_sha256 char(64) NOT NULL,
    generated_at timestamptz NOT NULL,
    generated_by text NOT NULL,
    supersedes_plan_id uuid,
    approved_at timestamptz,
    approved_by text,
    rejected_at timestamptz,
    rejected_by text,
    invalidated_at timestamptz,
    invalidation_reason text,
    applied_at timestamptz,
    applied_by text,
    failure_summary text,
    CONSTRAINT pk_import_plan PRIMARY KEY (import_plan_id),
    CONSTRAINT uq_import_plan_batch_plan UNIQUE (import_batch_id, import_plan_id),
    CONSTRAINT ck_import_plan_status CHECK (plan_status IN (
        'generated', 'awaiting_review', 'approved', 'rejected',
        'invalidated', 'applying', 'applied', 'failed'
    )),
    CONSTRAINT ck_import_plan_file_sha256 CHECK (file_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_plan_sha256 CHECK (plan_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_plan_fingerprint_sha256 CHECK (approval_fingerprint_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_plan_contract_nonempty CHECK (btrim(contract_version) <> ''),
    CONSTRAINT ck_import_plan_rules_nonempty CHECK (btrim(rules_version) <> ''),
    CONSTRAINT ck_import_plan_generated_by_nonempty CHECK (btrim(generated_by) <> ''),
    CONSTRAINT ck_import_plan_not_self_superseding CHECK (supersedes_plan_id IS NULL OR supersedes_plan_id <> import_plan_id),
    CONSTRAINT ck_import_plan_approval_pair CHECK (
        (approved_at IS NULL AND approved_by IS NULL)
        OR (approved_at IS NOT NULL AND approved_by IS NOT NULL)
    ),
    CONSTRAINT ck_import_plan_rejection_pair CHECK (
        (rejected_at IS NULL AND rejected_by IS NULL)
        OR (rejected_at IS NOT NULL AND rejected_by IS NOT NULL)
    ),
    CONSTRAINT ck_import_plan_application_pair CHECK (
        (applied_at IS NULL AND applied_by IS NULL)
        OR (applied_at IS NOT NULL AND applied_by IS NOT NULL)
    ),
    CONSTRAINT ck_import_plan_invalidation_pair CHECK (
        (invalidated_at IS NULL AND invalidation_reason IS NULL)
        OR (invalidated_at IS NOT NULL AND invalidation_reason IS NOT NULL)
    ),
    CONSTRAINT ck_import_plan_approved_evidence CHECK (
        plan_status NOT IN ('approved', 'applying', 'applied') OR approved_at IS NOT NULL
    ),
    CONSTRAINT ck_import_plan_rejected_evidence CHECK (plan_status <> 'rejected' OR rejected_at IS NOT NULL),
    CONSTRAINT ck_import_plan_invalidated_evidence CHECK (plan_status <> 'invalidated' OR invalidated_at IS NOT NULL),
    CONSTRAINT ck_import_plan_applied_evidence CHECK ((plan_status = 'applied') = (applied_at IS NOT NULL)),
    CONSTRAINT ck_import_plan_approval_time CHECK (approved_at IS NULL OR approved_at >= generated_at),
    CONSTRAINT ck_import_plan_rejection_time CHECK (rejected_at IS NULL OR rejected_at >= generated_at),
    CONSTRAINT ck_import_plan_invalidation_time CHECK (invalidated_at IS NULL OR invalidated_at >= generated_at),
    CONSTRAINT ck_import_plan_application_time CHECK (applied_at IS NULL OR applied_at >= generated_at)
);

-- Catalog dimensions and products.
CREATE TABLE perfect_catalog.brand (
    brand_id uuid NOT NULL,
    source_system_id uuid,
    source_brand_id text,
    code text NOT NULL,
    name text NOT NULL,
    normalized_name text NOT NULL,
    is_active boolean NOT NULL DEFAULT true,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_brand PRIMARY KEY (brand_id),
    CONSTRAINT uq_brand_code UNIQUE (code),
    CONSTRAINT ck_brand_code_nonempty CHECK (btrim(code) <> ''),
    CONSTRAINT ck_brand_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_brand_normalized_name_nonempty CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_brand_source_pair CHECK (source_brand_id IS NULL OR source_system_id IS NOT NULL),
    CONSTRAINT ck_brand_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.product_category (
    product_category_id uuid NOT NULL,
    parent_category_id uuid,
    source_system_id uuid,
    source_category_id text,
    name text NOT NULL,
    normalized_name text NOT NULL,
    source_path text,
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_product_category PRIMARY KEY (product_category_id),
    CONSTRAINT ck_product_category_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_product_category_normalized_name_nonempty CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_product_category_not_self_parent CHECK (
        parent_category_id IS NULL OR parent_category_id <> product_category_id
    ),
    CONSTRAINT ck_product_category_source_pair CHECK (source_category_id IS NULL OR source_system_id IS NOT NULL),
    CONSTRAINT ck_product_category_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.product_template (
    product_template_id uuid NOT NULL,
    source_system_id uuid NOT NULL,
    brand_id uuid NOT NULL,
    product_category_id uuid,
    odoo_template_id text,
    odoo_external_id text,
    name_original text NOT NULL,
    name_normalized text,
    currency_code text,
    uom_original text,
    activity_state text,
    is_favorite boolean,
    show_quantity_status boolean,
    source_active boolean,
    catalog_status text NOT NULL DEFAULT 'pending_review',
    variant_count_observed integer NOT NULL,
    source_updated_at timestamptz,
    created_from_staging_row_id uuid NOT NULL,
    last_confirmed_batch_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_product_template PRIMARY KEY (product_template_id),
    CONSTRAINT ck_product_template_name_nonempty CHECK (btrim(name_original) <> ''),
    CONSTRAINT ck_product_template_variant_count CHECK (variant_count_observed >= 0),
    CONSTRAINT ck_product_template_catalog_status CHECK (
        catalog_status IN ('pending_review', 'active', 'inactive', 'archived')
    ),
    CONSTRAINT ck_product_template_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.product_variant (
    product_variant_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    source_system_id uuid NOT NULL,
    odoo_variant_id text,
    odoo_external_id text,
    variant_name text,
    attributes jsonb,
    source_active boolean,
    catalog_status text NOT NULL DEFAULT 'pending_review',
    created_from_staging_row_id uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_product_variant PRIMARY KEY (product_variant_id),
    CONSTRAINT uq_product_variant_template_variant UNIQUE (product_template_id, product_variant_id),
    CONSTRAINT ck_product_variant_real_identifier CHECK (
        odoo_variant_id IS NOT NULL OR odoo_external_id IS NOT NULL
    ),
    CONSTRAINT ck_product_variant_catalog_status CHECK (
        catalog_status IN ('pending_review', 'active', 'inactive', 'archived')
    ),
    CONSTRAINT ck_product_variant_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

-- Plan items follow products so composite variant coherence can be enforced.
CREATE TABLE perfect_catalog.import_plan_item (
    import_plan_item_id uuid NOT NULL,
    import_plan_id uuid NOT NULL,
    item_order integer NOT NULL,
    staging_row_id uuid NOT NULL,
    product_template_id uuid,
    product_variant_id uuid,
    operation_type text NOT NULL,
    before_values jsonb NOT NULL,
    proposed_values jsonb NOT NULL,
    issues jsonb NOT NULL,
    requires_review boolean NOT NULL,
    human_decision text,
    decision_reason text,
    decided_at timestamptz,
    decided_by text,
    item_sha256 char(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_import_plan_item PRIMARY KEY (import_plan_item_id),
    CONSTRAINT uq_import_plan_item_order UNIQUE (import_plan_id, item_order),
    CONSTRAINT ck_import_plan_item_order CHECK (item_order >= 1),
    CONSTRAINT ck_import_plan_item_operation CHECK (operation_type IN (
        'create', 'update', 'no_change', 'conflict', 'blocked',
        'inventory_snapshot', 'media_pending', 'extraction_candidate'
    )),
    CONSTRAINT ck_import_plan_item_sha256 CHECK (item_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_import_plan_item_variant_template CHECK (
        product_variant_id IS NULL OR product_template_id IS NOT NULL
    ),
    CONSTRAINT ck_import_plan_item_decision_actor CHECK (
        (human_decision IS NULL AND decided_at IS NULL AND decided_by IS NULL)
        OR (human_decision IS NOT NULL AND decided_at IS NOT NULL AND decided_by IS NOT NULL)
    )
);

CREATE TABLE perfect_catalog.product_reference (
    product_reference_id uuid NOT NULL,
    source_system_id uuid NOT NULL,
    brand_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    staging_row_id uuid,
    reference_type text NOT NULL,
    value_original text NOT NULL,
    value_normalized text NOT NULL,
    is_primary boolean NOT NULL,
    confidence numeric(5,4),
    review_status text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_product_reference PRIMARY KEY (product_reference_id),
    CONSTRAINT ck_product_reference_type_nonempty CHECK (btrim(reference_type) <> ''),
    CONSTRAINT ck_product_reference_original_nonempty CHECK (btrim(value_original) <> ''),
    CONSTRAINT ck_product_reference_normalized_nonempty CHECK (btrim(value_normalized) <> ''),
    CONSTRAINT ck_product_reference_confidence CHECK (confidence IS NULL OR confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_product_reference_review_status CHECK (
        review_status IS NULL OR review_status IN ('pending', 'approved', 'rejected')
    ),
    CONSTRAINT ck_product_reference_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.inventory_snapshot (
    inventory_snapshot_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    import_batch_id uuid NOT NULL,
    import_plan_id uuid NOT NULL,
    staging_row_id uuid NOT NULL,
    quantity_on_hand numeric NOT NULL,
    quantity_available numeric NOT NULL,
    uom_original text NOT NULL,
    captured_at timestamptz NOT NULL,
    source_updated_at timestamptz,
    source_date_serial numeric,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_inventory_snapshot PRIMARY KEY (inventory_snapshot_id),
    CONSTRAINT uq_inventory_snapshot_retry UNIQUE NULLS NOT DISTINCT (
        import_batch_id,
        import_plan_id,
        staging_row_id,
        product_template_id,
        product_variant_id
    ),
    CONSTRAINT ck_inventory_snapshot_uom_nonempty CHECK (btrim(uom_original) <> '')
);

-- Media metadata only; binary content remains in configurable physical storage.
CREATE TABLE perfect_catalog.media_asset (
    media_asset_id uuid NOT NULL,
    source_system_id uuid NOT NULL,
    created_from_staging_row_id uuid NOT NULL,
    status text NOT NULL,
    content_sha256 char(64),
    media_type text,
    byte_size bigint,
    storage_backend text,
    storage_uri text,
    original_filename text,
    error_code text,
    error_message text,
    processed_at timestamptz,
    metadata jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_media_asset PRIMARY KEY (media_asset_id),
    CONSTRAINT ck_media_asset_status CHECK (status IN (
        'presente', 'ausente', 'error_de_exportacion', 'invalida', 'procesada'
    )),
    CONSTRAINT ck_media_asset_sha256 CHECK (
        content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_media_asset_size CHECK (byte_size IS NULL OR byte_size >= 0),
    CONSTRAINT ck_media_asset_processed_fields CHECK (
        status <> 'procesada'
        OR (
            content_sha256 IS NOT NULL
            AND media_type IS NOT NULL
            AND byte_size IS NOT NULL
            AND storage_backend IS NOT NULL
            AND storage_uri IS NOT NULL
            AND processed_at IS NOT NULL
        )
    ),
    CONSTRAINT ck_media_asset_processed_at CHECK (processed_at IS NULL OR processed_at >= created_at)
);

CREATE TABLE perfect_catalog.product_media (
    product_media_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    media_asset_id uuid NOT NULL,
    role text NOT NULL,
    sort_order integer NOT NULL,
    caption text,
    is_primary boolean,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_product_media PRIMARY KEY (product_media_id),
    CONSTRAINT ck_product_media_role_nonempty CHECK (btrim(role) <> ''),
    CONSTRAINT ck_product_media_sort_order CHECK (sort_order >= 0)
);

-- Vehicle vocabulary and reviewable candidates.
CREATE TABLE perfect_catalog.vehicle_make (
    vehicle_make_id uuid NOT NULL,
    name text NOT NULL,
    normalized_name text NOT NULL,
    review_status text NOT NULL,
    source_code text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_vehicle_make PRIMARY KEY (vehicle_make_id),
    CONSTRAINT ck_vehicle_make_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_vehicle_make_normalized_nonempty CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_vehicle_make_review_status CHECK (review_status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT ck_vehicle_make_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.vehicle_model (
    vehicle_model_id uuid NOT NULL,
    vehicle_make_id uuid NOT NULL,
    name text NOT NULL,
    normalized_name text NOT NULL,
    review_status text NOT NULL,
    source_code text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_vehicle_model PRIMARY KEY (vehicle_model_id),
    CONSTRAINT ck_vehicle_model_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_vehicle_model_normalized_nonempty CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_vehicle_model_review_status CHECK (review_status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT ck_vehicle_model_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.vehicle_engine (
    vehicle_engine_id uuid NOT NULL,
    vehicle_model_id uuid,
    name text NOT NULL,
    normalized_name text NOT NULL,
    review_status text NOT NULL,
    engine_code text,
    displacement_liters numeric(6,3),
    cylinders smallint,
    attributes jsonb,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamptz,
    CONSTRAINT pk_vehicle_engine PRIMARY KEY (vehicle_engine_id),
    CONSTRAINT ck_vehicle_engine_name_nonempty CHECK (btrim(name) <> ''),
    CONSTRAINT ck_vehicle_engine_normalized_nonempty CHECK (btrim(normalized_name) <> ''),
    CONSTRAINT ck_vehicle_engine_review_status CHECK (review_status IN ('pending', 'approved', 'rejected')),
    CONSTRAINT ck_vehicle_engine_displacement CHECK (displacement_liters IS NULL OR displacement_liters > 0),
    CONSTRAINT ck_vehicle_engine_cylinders CHECK (cylinders IS NULL OR cylinders > 0),
    CONSTRAINT ck_vehicle_engine_updated_at CHECK (updated_at IS NULL OR updated_at >= created_at)
);

CREATE TABLE perfect_catalog.product_application_candidate (
    product_application_candidate_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    staging_row_id uuid NOT NULL,
    vehicle_make_id uuid,
    vehicle_model_id uuid,
    vehicle_engine_id uuid,
    evidence_original text NOT NULL,
    rule_code text NOT NULL,
    rule_version text NOT NULL,
    confidence numeric(5,4) NOT NULL,
    review_status text NOT NULL,
    year_from smallint,
    year_to smallint,
    position text,
    notes text,
    reviewed_by text,
    reviewed_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_product_application_candidate PRIMARY KEY (product_application_candidate_id),
    CONSTRAINT ck_product_application_evidence_nonempty CHECK (btrim(evidence_original) <> ''),
    CONSTRAINT ck_product_application_rule_code_nonempty CHECK (btrim(rule_code) <> ''),
    CONSTRAINT ck_product_application_rule_version_nonempty CHECK (btrim(rule_version) <> ''),
    CONSTRAINT ck_product_application_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_product_application_review_status CHECK (
        review_status IN ('pending', 'approved', 'rejected')
    ),
    CONSTRAINT ck_product_application_year_from CHECK (year_from IS NULL OR year_from > 0),
    CONSTRAINT ck_product_application_year_to CHECK (year_to IS NULL OR year_to > 0),
    CONSTRAINT ck_product_application_year_range CHECK (
        year_from IS NULL OR year_to IS NULL OR year_to >= year_from
    ),
    CONSTRAINT ck_product_application_review_pair CHECK (
        (reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    ),
    CONSTRAINT ck_product_application_reviewed_at CHECK (reviewed_at IS NULL OR reviewed_at >= created_at)
);

CREATE TABLE perfect_catalog.extraction_candidate (
    extraction_candidate_id uuid NOT NULL,
    staging_row_id uuid NOT NULL,
    product_template_id uuid,
    candidate_type text NOT NULL,
    evidence_original text NOT NULL,
    value_original text NOT NULL,
    value_normalized text NOT NULL,
    rule_code text NOT NULL,
    rule_version text NOT NULL,
    confidence numeric(5,4) NOT NULL,
    review_status text NOT NULL,
    target_field text,
    reviewed_by text,
    reviewed_at timestamptz,
    review_note text,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_extraction_candidate PRIMARY KEY (extraction_candidate_id),
    CONSTRAINT ck_extraction_candidate_type_nonempty CHECK (btrim(candidate_type) <> ''),
    CONSTRAINT ck_extraction_candidate_evidence_nonempty CHECK (btrim(evidence_original) <> ''),
    CONSTRAINT ck_extraction_candidate_value_original_nonempty CHECK (btrim(value_original) <> ''),
    CONSTRAINT ck_extraction_candidate_rule_code_nonempty CHECK (btrim(rule_code) <> ''),
    CONSTRAINT ck_extraction_candidate_rule_version_nonempty CHECK (btrim(rule_version) <> ''),
    CONSTRAINT ck_extraction_candidate_confidence CHECK (confidence BETWEEN 0 AND 1),
    CONSTRAINT ck_extraction_candidate_review_status CHECK (
        review_status IN ('pending', 'approved', 'rejected')
    ),
    CONSTRAINT ck_extraction_candidate_review_pair CHECK (
        (reviewed_by IS NULL AND reviewed_at IS NULL)
        OR (reviewed_by IS NOT NULL AND reviewed_at IS NOT NULL)
    ),
    CONSTRAINT ck_extraction_candidate_reviewed_at CHECK (reviewed_at IS NULL OR reviewed_at >= created_at)
);

-- Immutable catalog publication snapshots.
CREATE TABLE perfect_catalog.catalog_release (
    catalog_release_id uuid NOT NULL,
    brand_id uuid NOT NULL,
    version text NOT NULL,
    status text NOT NULL,
    definition jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by text NOT NULL,
    published_at timestamptz,
    published_by text,
    archived_at timestamptz,
    notes text,
    snapshot_sha256 char(64),
    CONSTRAINT pk_catalog_release PRIMARY KEY (catalog_release_id),
    CONSTRAINT uq_catalog_release_brand_version UNIQUE (brand_id, version),
    CONSTRAINT ck_catalog_release_version_nonempty CHECK (btrim(version) <> ''),
    CONSTRAINT ck_catalog_release_created_by_nonempty CHECK (btrim(created_by) <> ''),
    CONSTRAINT ck_catalog_release_status CHECK (status IN ('draft', 'published', 'archived')),
    CONSTRAINT ck_catalog_release_sha256 CHECK (
        snapshot_sha256 IS NULL OR snapshot_sha256 ~ '^[0-9a-f]{64}$'
    ),
    CONSTRAINT ck_catalog_release_publish_pair CHECK (
        (published_at IS NULL AND published_by IS NULL)
        OR (published_at IS NOT NULL AND published_by IS NOT NULL)
    ),
    CONSTRAINT ck_catalog_release_published_evidence CHECK (
        status <> 'published'
        OR (published_at IS NOT NULL AND published_by IS NOT NULL AND snapshot_sha256 IS NOT NULL)
    ),
    CONSTRAINT ck_catalog_release_archived_evidence CHECK (
        status <> 'archived' OR archived_at IS NOT NULL
    ),
    CONSTRAINT ck_catalog_release_published_at CHECK (published_at IS NULL OR published_at >= created_at),
    CONSTRAINT ck_catalog_release_archived_at CHECK (archived_at IS NULL OR archived_at >= created_at)
);

CREATE TABLE perfect_catalog.catalog_release_item (
    catalog_release_item_id uuid NOT NULL,
    catalog_release_id uuid NOT NULL,
    product_template_id uuid NOT NULL,
    product_variant_id uuid,
    item_order integer NOT NULL,
    snapshot_schema_version text NOT NULL,
    snapshot_data jsonb NOT NULL,
    snapshot_sha256 char(64) NOT NULL,
    section_key text,
    grouping_keys jsonb,
    source_import_batch_id uuid,
    created_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT pk_catalog_release_item PRIMARY KEY (catalog_release_item_id),
    CONSTRAINT uq_catalog_release_item_order UNIQUE (catalog_release_id, item_order),
    CONSTRAINT ck_catalog_release_item_order CHECK (item_order >= 1),
    CONSTRAINT ck_catalog_release_item_schema_nonempty CHECK (btrim(snapshot_schema_version) <> ''),
    CONSTRAINT ck_catalog_release_item_sha256 CHECK (snapshot_sha256 ~ '^[0-9a-f]{64}$')
);

-- Append-only audit ledger. entity_id is intentionally not a polymorphic FK.
CREATE TABLE perfect_catalog.audit_event (
    audit_event_id uuid NOT NULL,
    import_batch_id uuid,
    import_plan_id uuid,
    staging_row_id uuid,
    event_type text NOT NULL,
    entity_type text NOT NULL,
    entity_id uuid NOT NULL,
    occurred_at timestamptz NOT NULL,
    actor_type text NOT NULL,
    actor_id text NOT NULL,
    before_data jsonb,
    after_data jsonb NOT NULL,
    reason text,
    correlation_id uuid,
    metadata jsonb,
    event_sha256 char(64) NOT NULL,
    CONSTRAINT pk_audit_event PRIMARY KEY (audit_event_id),
    CONSTRAINT ck_audit_event_type_nonempty CHECK (btrim(event_type) <> ''),
    CONSTRAINT ck_audit_entity_type_nonempty CHECK (btrim(entity_type) <> ''),
    CONSTRAINT ck_audit_actor_type_nonempty CHECK (btrim(actor_type) <> ''),
    CONSTRAINT ck_audit_actor_id_nonempty CHECK (btrim(actor_id) <> ''),
    CONSTRAINT ck_audit_event_sha256 CHECK (event_sha256 ~ '^[0-9a-f]{64}$'),
    CONSTRAINT ck_audit_human_reason CHECK (
        actor_type <> 'human' OR (reason IS NOT NULL AND btrim(reason) <> '')
    )
);

-- Foreign keys are added after all tables exist. Every delete action is restrictive.
ALTER TABLE perfect_catalog.import_batch
    ADD CONSTRAINT fk_import_batch_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.import_file
    ADD CONSTRAINT fk_import_file_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_file_duplicate
    FOREIGN KEY (duplicate_of_file_id) REFERENCES perfect_catalog.import_file (import_file_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.staging_row
    ADD CONSTRAINT fk_staging_row_file
    FOREIGN KEY (import_file_id) REFERENCES perfect_catalog.import_file (import_file_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.staging_row_result
    ADD CONSTRAINT fk_staging_row_result_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_staging_row_result_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.import_issue
    ADD CONSTRAINT fk_import_issue_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_issue_file
    FOREIGN KEY (import_batch_id, import_file_id)
    REFERENCES perfect_catalog.import_file (import_batch_id, import_file_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_issue_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_issue_result
    FOREIGN KEY (staging_row_result_id) REFERENCES perfect_catalog.staging_row_result (staging_row_result_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.import_plan
    ADD CONSTRAINT fk_import_plan_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_plan_file_in_batch
    FOREIGN KEY (import_batch_id, import_file_id)
    REFERENCES perfect_catalog.import_file (import_batch_id, import_file_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_plan_superseded
    FOREIGN KEY (supersedes_plan_id) REFERENCES perfect_catalog.import_plan (import_plan_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.brand
    ADD CONSTRAINT fk_brand_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_category
    ADD CONSTRAINT fk_product_category_parent
    FOREIGN KEY (parent_category_id) REFERENCES perfect_catalog.product_category (product_category_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_category_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_template
    ADD CONSTRAINT fk_product_template_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_template_brand
    FOREIGN KEY (brand_id) REFERENCES perfect_catalog.brand (brand_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_template_category
    FOREIGN KEY (product_category_id) REFERENCES perfect_catalog.product_category (product_category_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_template_created_row
    FOREIGN KEY (created_from_staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_template_last_batch
    FOREIGN KEY (last_confirmed_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_variant
    ADD CONSTRAINT fk_product_variant_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_variant_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_variant_created_row
    FOREIGN KEY (created_from_staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.import_plan_item
    ADD CONSTRAINT fk_import_plan_item_plan
    FOREIGN KEY (import_plan_id) REFERENCES perfect_catalog.import_plan (import_plan_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_plan_item_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_plan_item_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_import_plan_item_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (product_template_id, product_variant_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_reference
    ADD CONSTRAINT fk_product_reference_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_reference_brand
    FOREIGN KEY (brand_id) REFERENCES perfect_catalog.brand (brand_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_reference_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_reference_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (product_template_id, product_variant_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_reference_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.inventory_snapshot
    ADD CONSTRAINT fk_inventory_snapshot_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (product_template_id, product_variant_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_plan_in_batch
    FOREIGN KEY (import_batch_id, import_plan_id)
    REFERENCES perfect_catalog.import_plan (import_batch_id, import_plan_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_inventory_snapshot_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.media_asset
    ADD CONSTRAINT fk_media_asset_source_system
    FOREIGN KEY (source_system_id) REFERENCES perfect_catalog.source_system (source_system_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_media_asset_created_row
    FOREIGN KEY (created_from_staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_media
    ADD CONSTRAINT fk_product_media_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_media_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (product_template_id, product_variant_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_media_asset
    FOREIGN KEY (media_asset_id) REFERENCES perfect_catalog.media_asset (media_asset_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.vehicle_model
    ADD CONSTRAINT fk_vehicle_model_make
    FOREIGN KEY (vehicle_make_id) REFERENCES perfect_catalog.vehicle_make (vehicle_make_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.vehicle_engine
    ADD CONSTRAINT fk_vehicle_engine_model
    FOREIGN KEY (vehicle_model_id) REFERENCES perfect_catalog.vehicle_model (vehicle_model_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.product_application_candidate
    ADD CONSTRAINT fk_product_application_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_application_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_application_make
    FOREIGN KEY (vehicle_make_id) REFERENCES perfect_catalog.vehicle_make (vehicle_make_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_application_model
    FOREIGN KEY (vehicle_model_id) REFERENCES perfect_catalog.vehicle_model (vehicle_model_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_product_application_engine
    FOREIGN KEY (vehicle_engine_id) REFERENCES perfect_catalog.vehicle_engine (vehicle_engine_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.extraction_candidate
    ADD CONSTRAINT fk_extraction_candidate_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_extraction_candidate_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.catalog_release
    ADD CONSTRAINT fk_catalog_release_brand
    FOREIGN KEY (brand_id) REFERENCES perfect_catalog.brand (brand_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.catalog_release_item
    ADD CONSTRAINT fk_catalog_release_item_release
    FOREIGN KEY (catalog_release_id) REFERENCES perfect_catalog.catalog_release (catalog_release_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_catalog_release_item_template
    FOREIGN KEY (product_template_id) REFERENCES perfect_catalog.product_template (product_template_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_catalog_release_item_variant
    FOREIGN KEY (product_template_id, product_variant_id)
    REFERENCES perfect_catalog.product_variant (product_template_id, product_variant_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_catalog_release_item_batch
    FOREIGN KEY (source_import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT;

ALTER TABLE perfect_catalog.audit_event
    ADD CONSTRAINT fk_audit_event_batch
    FOREIGN KEY (import_batch_id) REFERENCES perfect_catalog.import_batch (import_batch_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_audit_event_plan
    FOREIGN KEY (import_plan_id) REFERENCES perfect_catalog.import_plan (import_plan_id) ON DELETE RESTRICT,
    ADD CONSTRAINT fk_audit_event_row
    FOREIGN KEY (staging_row_id) REFERENCES perfect_catalog.staging_row (staging_row_id) ON DELETE RESTRICT;

-- Contextual uniqueness and reconciliation indexes.
CREATE INDEX ix_source_system_active
    ON perfect_catalog.source_system (is_active);

CREATE INDEX ix_import_batch_source_started
    ON perfect_catalog.import_batch (source_system_id, started_at DESC);
CREATE INDEX ix_import_batch_status
    ON perfect_catalog.import_batch (status);

CREATE INDEX ix_import_file_sha256
    ON perfect_catalog.import_file (sha256);
CREATE INDEX ix_import_file_batch_name
    ON perfect_catalog.import_file (import_batch_id, original_name);
CREATE INDEX ix_import_file_duplicate
    ON perfect_catalog.import_file (duplicate_of_file_id);

CREATE INDEX ix_staging_row_sha256
    ON perfect_catalog.staging_row (row_sha256);

CREATE INDEX ix_staging_row_result_row_stage_created
    ON perfect_catalog.staging_row_result (staging_row_id, processing_stage, created_at DESC);
CREATE INDEX ix_staging_row_result_batch
    ON perfect_catalog.staging_row_result (import_batch_id);
CREATE INDEX ix_staging_row_result_versions
    ON perfect_catalog.staging_row_result (contract_version, rules_version);
CREATE INDEX ix_staging_row_result_status
    ON perfect_catalog.staging_row_result (status);

CREATE INDEX ix_import_issue_batch_severity_status
    ON perfect_catalog.import_issue (import_batch_id, severity, status);
CREATE INDEX ix_import_issue_row
    ON perfect_catalog.import_issue (staging_row_id);
CREATE INDEX ix_import_issue_result
    ON perfect_catalog.import_issue (staging_row_result_id);
CREATE INDEX ix_import_issue_code
    ON perfect_catalog.import_issue (code);

CREATE INDEX ix_import_plan_batch_generated
    ON perfect_catalog.import_plan (import_batch_id, generated_at DESC);
CREATE INDEX ix_import_plan_file
    ON perfect_catalog.import_plan (import_file_id);
CREATE INDEX ix_import_plan_status
    ON perfect_catalog.import_plan (plan_status);
CREATE INDEX ix_import_plan_sha256
    ON perfect_catalog.import_plan (plan_sha256);
CREATE INDEX ix_import_plan_supersedes
    ON perfect_catalog.import_plan (supersedes_plan_id);

CREATE UNIQUE INDEX uq_brand_source_id
    ON perfect_catalog.brand (source_system_id, source_brand_id)
    WHERE source_system_id IS NOT NULL AND source_brand_id IS NOT NULL;
CREATE INDEX ix_brand_normalized_name
    ON perfect_catalog.brand (normalized_name);

CREATE UNIQUE INDEX uq_product_category_source_id
    ON perfect_catalog.product_category (source_system_id, source_category_id)
    WHERE source_system_id IS NOT NULL AND source_category_id IS NOT NULL;
CREATE INDEX ix_product_category_parent
    ON perfect_catalog.product_category (parent_category_id);
CREATE INDEX ix_product_category_normalized_name
    ON perfect_catalog.product_category (normalized_name);

CREATE UNIQUE INDEX uq_product_template_odoo_id
    ON perfect_catalog.product_template (source_system_id, odoo_template_id)
    WHERE odoo_template_id IS NOT NULL;
CREATE UNIQUE INDEX uq_product_template_external_id
    ON perfect_catalog.product_template (source_system_id, odoo_external_id)
    WHERE odoo_external_id IS NOT NULL;
CREATE INDEX ix_product_template_source_brand
    ON perfect_catalog.product_template (source_system_id, brand_id);
CREATE INDEX ix_product_template_category
    ON perfect_catalog.product_template (product_category_id);
CREATE INDEX ix_product_template_catalog_status
    ON perfect_catalog.product_template (catalog_status);
CREATE INDEX ix_product_template_name_normalized
    ON perfect_catalog.product_template (name_normalized);
CREATE INDEX ix_product_template_last_batch
    ON perfect_catalog.product_template (last_confirmed_batch_id);

CREATE UNIQUE INDEX uq_product_variant_odoo_id
    ON perfect_catalog.product_variant (source_system_id, odoo_variant_id)
    WHERE odoo_variant_id IS NOT NULL;
CREATE UNIQUE INDEX uq_product_variant_external_id
    ON perfect_catalog.product_variant (source_system_id, odoo_external_id)
    WHERE odoo_external_id IS NOT NULL;
CREATE INDEX ix_product_variant_template
    ON perfect_catalog.product_variant (product_template_id);
CREATE INDEX ix_product_variant_catalog_status
    ON perfect_catalog.product_variant (catalog_status);

CREATE INDEX ix_import_plan_item_plan
    ON perfect_catalog.import_plan_item (import_plan_id);
CREATE INDEX ix_import_plan_item_row
    ON perfect_catalog.import_plan_item (staging_row_id);
CREATE INDEX ix_import_plan_item_product
    ON perfect_catalog.import_plan_item (product_template_id, product_variant_id);
CREATE INDEX ix_import_plan_item_operation
    ON perfect_catalog.import_plan_item (operation_type);
CREATE INDEX ix_import_plan_item_review
    ON perfect_catalog.import_plan_item (requires_review)
    WHERE requires_review IS TRUE;

CREATE INDEX ix_product_reference_reconciliation
    ON perfect_catalog.product_reference (source_system_id, brand_id, value_normalized);
CREATE INDEX ix_product_reference_product_type
    ON perfect_catalog.product_reference (product_template_id, product_variant_id, reference_type);
CREATE INDEX ix_product_reference_review_status
    ON perfect_catalog.product_reference (review_status)
    WHERE review_status IS NOT NULL;

CREATE INDEX ix_inventory_snapshot_template_captured
    ON perfect_catalog.inventory_snapshot (product_template_id, captured_at DESC);
CREATE INDEX ix_inventory_snapshot_variant_captured
    ON perfect_catalog.inventory_snapshot (product_variant_id, captured_at DESC)
    WHERE product_variant_id IS NOT NULL;
CREATE INDEX ix_inventory_snapshot_batch
    ON perfect_catalog.inventory_snapshot (import_batch_id);
CREATE INDEX ix_inventory_snapshot_plan
    ON perfect_catalog.inventory_snapshot (import_plan_id);

CREATE UNIQUE INDEX uq_media_asset_content_sha256
    ON perfect_catalog.media_asset (content_sha256)
    WHERE content_sha256 IS NOT NULL;
CREATE INDEX ix_media_asset_status
    ON perfect_catalog.media_asset (status);
CREATE INDEX ix_media_asset_created_row
    ON perfect_catalog.media_asset (created_from_staging_row_id);

CREATE UNIQUE INDEX uq_product_media_template_asset_role
    ON perfect_catalog.product_media (product_template_id, media_asset_id, role)
    WHERE product_variant_id IS NULL;
CREATE UNIQUE INDEX uq_product_media_variant_asset_role
    ON perfect_catalog.product_media (product_variant_id, media_asset_id, role)
    WHERE product_variant_id IS NOT NULL;
CREATE UNIQUE INDEX uq_product_media_primary_template_role
    ON perfect_catalog.product_media (product_template_id, role)
    WHERE product_variant_id IS NULL AND is_primary IS TRUE;
CREATE UNIQUE INDEX uq_product_media_primary_variant_role
    ON perfect_catalog.product_media (product_variant_id, role)
    WHERE product_variant_id IS NOT NULL AND is_primary IS TRUE;
CREATE INDEX ix_product_media_asset
    ON perfect_catalog.product_media (media_asset_id);

CREATE UNIQUE INDEX uq_vehicle_make_approved_name
    ON perfect_catalog.vehicle_make (normalized_name)
    WHERE review_status = 'approved';
CREATE INDEX ix_vehicle_make_review_status
    ON perfect_catalog.vehicle_make (review_status);

CREATE UNIQUE INDEX uq_vehicle_model_approved_name
    ON perfect_catalog.vehicle_model (vehicle_make_id, normalized_name)
    WHERE review_status = 'approved';
CREATE INDEX ix_vehicle_model_make
    ON perfect_catalog.vehicle_model (vehicle_make_id);
CREATE INDEX ix_vehicle_model_review_status
    ON perfect_catalog.vehicle_model (review_status);

CREATE INDEX ix_vehicle_engine_model
    ON perfect_catalog.vehicle_engine (vehicle_model_id);
CREATE INDEX ix_vehicle_engine_code
    ON perfect_catalog.vehicle_engine (engine_code);
CREATE INDEX ix_vehicle_engine_normalized_name
    ON perfect_catalog.vehicle_engine (normalized_name);
CREATE INDEX ix_vehicle_engine_review_status
    ON perfect_catalog.vehicle_engine (review_status);

CREATE INDEX ix_product_application_product
    ON perfect_catalog.product_application_candidate (product_template_id);
CREATE INDEX ix_product_application_review_status
    ON perfect_catalog.product_application_candidate (review_status);
CREATE INDEX ix_product_application_vehicle
    ON perfect_catalog.product_application_candidate (vehicle_make_id, vehicle_model_id, vehicle_engine_id);
CREATE INDEX ix_product_application_years
    ON perfect_catalog.product_application_candidate (year_from, year_to);

CREATE INDEX ix_extraction_candidate_type_review
    ON perfect_catalog.extraction_candidate (candidate_type, review_status);
CREATE INDEX ix_extraction_candidate_row
    ON perfect_catalog.extraction_candidate (staging_row_id);
CREATE INDEX ix_extraction_candidate_product
    ON perfect_catalog.extraction_candidate (product_template_id);

CREATE INDEX ix_catalog_release_brand_status
    ON perfect_catalog.catalog_release (brand_id, status);
CREATE INDEX ix_catalog_release_published_at
    ON perfect_catalog.catalog_release (published_at DESC);
CREATE INDEX ix_catalog_release_snapshot_sha256
    ON perfect_catalog.catalog_release (snapshot_sha256)
    WHERE snapshot_sha256 IS NOT NULL;

CREATE INDEX ix_catalog_release_item_product
    ON perfect_catalog.catalog_release_item (product_template_id, product_variant_id);
CREATE INDEX ix_catalog_release_item_section
    ON perfect_catalog.catalog_release_item (section_key);
CREATE INDEX ix_catalog_release_item_snapshot_sha256
    ON perfect_catalog.catalog_release_item (snapshot_sha256);

CREATE INDEX ix_audit_event_entity_occurred
    ON perfect_catalog.audit_event (entity_type, entity_id, occurred_at);
CREATE INDEX ix_audit_event_batch
    ON perfect_catalog.audit_event (import_batch_id);
CREATE INDEX ix_audit_event_plan
    ON perfect_catalog.audit_event (import_plan_id);
CREATE INDEX ix_audit_event_correlation
    ON perfect_catalog.audit_event (correlation_id);
CREATE INDEX ix_audit_event_type
    ON perfect_catalog.audit_event (event_type);

COMMIT;
