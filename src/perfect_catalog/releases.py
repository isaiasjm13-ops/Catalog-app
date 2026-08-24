from __future__ import annotations

import uuid
from typing import Any, Iterable

from .canonical import canonical_sha256


SNAPSHOT_SCHEMA_VERSION = "catalog-product-v1"
RELEASE_HASH_ALGORITHM = "catalog-release-v1"


def product_snapshot_sha256(snapshot_data: dict[str, Any]) -> str:
    return canonical_sha256(snapshot_data)


def release_snapshot_sha256(
    brand_id: uuid.UUID,
    version: str,
    items: Iterable[dict[str, Any]],
) -> str:
    evidence = {
        "algorithm": RELEASE_HASH_ALGORITHM,
        "brand_id": brand_id,
        "version": version,
        "items": [
            {
                "item_order": item["item_order"],
                "product_template_id": item["product_template_id"],
                "product_variant_id": item.get("product_variant_id"),
                "snapshot_schema_version": item["snapshot_schema_version"],
                "snapshot_sha256": item["snapshot_sha256"],
            }
            for item in items
        ],
    }
    return canonical_sha256(evidence)


def validate_release_item(item: dict[str, Any]) -> None:
    if item["snapshot_schema_version"] != SNAPSHOT_SCHEMA_VERSION:
        raise ValueError(
            "El release usa un schema de snapshot no soportado: "
            f"{item['snapshot_schema_version']!r}."
        )
    data = item["snapshot_data"]
    if not isinstance(data, dict):
        raise ValueError("snapshot_data debe ser un objeto JSON.")
    required_text = (
        "product_template_id",
        "internal_reference_original",
        "internal_reference_normalized",
        "name_original",
        "name_normalized",
    )
    for field in required_text:
        if not isinstance(data.get(field), str) or not data[field].strip():
            raise ValueError(f"El snapshot publicado requiere {field} no vacío.")
    try:
        snapshot_template_id = uuid.UUID(data["product_template_id"])
    except ValueError as exc:
        raise ValueError("product_template_id del snapshot no es un UUID válido.") from exc
    if snapshot_template_id != item["product_template_id"]:
        raise ValueError("La identidad del snapshot no coincide con catalog_release_item.")
    snapshot_variant = data.get("product_variant_id")
    expected_variant = item.get("product_variant_id")
    if snapshot_variant is not None:
        try:
            snapshot_variant = uuid.UUID(str(snapshot_variant))
        except ValueError as exc:
            raise ValueError("product_variant_id del snapshot no es un UUID válido.") from exc
    if snapshot_variant != expected_variant:
        raise ValueError("La variante del snapshot no coincide con catalog_release_item.")
    quantity = data.get("quantity_available")
    if quantity is not None and (
        isinstance(quantity, bool) or not isinstance(quantity, (int, float))
    ):
        raise ValueError("quantity_available debe ser numérica o nula.")
    recalculated = product_snapshot_sha256(data)
    if recalculated != item["snapshot_sha256"]:
        raise ValueError("snapshot_data no coincide con snapshot_sha256.")


def validate_release_items(items: Iterable[dict[str, Any]]) -> None:
    public_ids: set[uuid.UUID] = set()
    for item in items:
        validate_release_item(item)
        public_id = item.get("product_variant_id") or item["product_template_id"]
        if public_id in public_ids:
            raise ValueError(f"El release repite la identidad pública {public_id}.")
        public_ids.add(public_id)
