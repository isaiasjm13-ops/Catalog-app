from __future__ import annotations

import copy
import unittest
import uuid

from perfect_catalog.releases import (
    SNAPSHOT_SCHEMA_VERSION,
    product_snapshot_sha256,
    release_snapshot_sha256,
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


class ReleaseIntegrityTests(unittest.TestCase):
    def test_valid_snapshot_and_release_hash_are_stable(self) -> None:
        item = make_release_item()
        validate_release_item(item)
        brand_id = uuid.uuid4()
        self.assertEqual(
            release_snapshot_sha256(brand_id, "2026.08.1", [item]),
            release_snapshot_sha256(brand_id, "2026.08.1", [item]),
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
        normal = release_snapshot_sha256(brand_id, "v1", [first, second])
        reversed_order = release_snapshot_sha256(brand_id, "v1", [second, first])
        self.assertNotEqual(normal, reversed_order)

    def test_duplicate_public_identity_is_rejected(self) -> None:
        first = make_release_item(1)
        second = copy.deepcopy(first)
        second["item_order"] = 2
        with self.assertRaisesRegex(ValueError, "repite la identidad pública"):
            validate_release_items([first, second])


if __name__ == "__main__":
    unittest.main()
