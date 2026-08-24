from __future__ import annotations

import copy
import unittest
import uuid

from perfect_catalog.releases import (
    SNAPSHOT_SCHEMA_VERSION,
    product_snapshot_sha256,
    release_snapshot_sha256,
    validate_release_definition,
    validate_release_item,
    validate_release_items,
)


def make_release_item(order: int = 1) -> dict[str, object]:
    product_id = uuid.uuid4()
    data = {
        "product_template_id": str(product_id),
        "product_variant_id": None,
        "internal_reference_original": "PT-001",
        "internal_reference_normalized": "PT-001",
        "name_original": "Producto publicado",
        "name_normalized": "PRODUCTO PUBLICADO",
        "category_path": "Empaques / Motor",
        "quantity_available": -2,
        "image_status": "absent",
        "brand": "NATSUKI",
        "family": "empaques",
    }
    return {
        "item_order": order,
        "product_template_id": product_id,
        "product_variant_id": None,
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "snapshot_data": data,
        "snapshot_sha256": product_snapshot_sha256(data),
    }


def make_definition() -> dict[str, object]:
    return {
        "snapshot_schema_version": SNAPSHOT_SCHEMA_VERSION,
        "release_hash_algorithm": "catalog-release-v2",
        "source_kind": "applied_catalog",
        "source_plan_id": str(uuid.uuid4()),
        "source_plan_fingerprint_sha256": "a" * 64,
        "source_import_batch_id": str(uuid.uuid4()),
        "contract_version": "test-contract",
        "rules_version": "test-rules",
        "selection": {"brand": "NATSUKI"},
        "item_count": 1,
    }


class ReleaseIntegrityTests(unittest.TestCase):
    def test_valid_snapshot_and_release_hash_are_stable(self) -> None:
        item = make_release_item()
        validate_release_item(item)
        brand_id = uuid.uuid4()
        definition = make_definition()
        self.assertEqual(
            release_snapshot_sha256(brand_id, "2026.08.1", definition, [item]),
            release_snapshot_sha256(brand_id, "2026.08.1", definition, [item]),
        )

    def test_tampered_snapshot_is_rejected(self) -> None:
        item = make_release_item()
        changed = copy.deepcopy(item)
        changed["snapshot_data"]["name_original"] = "Alterado"  # type: ignore[index]
        with self.assertRaisesRegex(ValueError, "snapshot_sha256"):
            validate_release_item(changed)

    def test_relational_identity_mismatch_is_rejected(self) -> None:
        item = make_release_item()
        item["product_template_id"] = uuid.uuid4()
        with self.assertRaisesRegex(ValueError, "identidad"):
            validate_release_item(item)

    def test_unknown_snapshot_schema_is_rejected(self) -> None:
        item = make_release_item()
        item["snapshot_schema_version"] = "future-v99"
        with self.assertRaisesRegex(ValueError, "no soportado"):
            validate_release_item(item)

    def test_release_hash_commits_to_item_order(self) -> None:
        brand_id = uuid.uuid4()
        first = make_release_item(1)
        second = make_release_item(2)
        definition = make_definition()
        normal = release_snapshot_sha256(brand_id, "v1", definition, [first, second])
        reversed_order = release_snapshot_sha256(
            brand_id, "v1", definition, [second, first]
        )
        self.assertNotEqual(normal, reversed_order)

    def test_release_hash_commits_to_definition(self) -> None:
        brand_id = uuid.uuid4()
        item = make_release_item()
        first = make_definition()
        changed = {**first, "selection": {"catalog_status": "active"}}
        self.assertNotEqual(
            release_snapshot_sha256(brand_id, "v1", first, [item]),
            release_snapshot_sha256(brand_id, "v1", changed, [item]),
        )

    def test_duplicate_public_identity_is_rejected(self) -> None:
        first = make_release_item(1)
        second = copy.deepcopy(first)
        second["item_order"] = 2
        with self.assertRaisesRegex(ValueError, "repite la identidad pública"):
            validate_release_items([first, second])

    def test_release_definition_requires_provenance_and_exact_count(self) -> None:
        definition = make_definition()
        validate_release_definition(definition, 1)
        for changed in (
            {**definition, "item_count": 2},
            {**definition, "source_plan_fingerprint_sha256": "bad"},
            {**definition, "selection": None},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(ValueError):
                    validate_release_definition(changed, 1)


if __name__ == "__main__":
    unittest.main()
