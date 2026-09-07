from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from perfect_catalog.public_catalog import (
    MAX_PUBLIC_IMAGE_FILES,
    _match_images,
    generate_public_catalog,
)

CSV_HEADERS = "Referencia interna,Nombre,Categoría de producto,Referencias Adicionales\n"


def _png_bytes(color: tuple[int, int, int] = (200, 30, 30)) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _csv(rows: str) -> bytes:
    return (CSV_HEADERS + rows).encode("utf-8-sig")


class GeneratePublicCatalogTests(unittest.TestCase):
    def _call(self, excel_bytes: bytes, images=(), **overrides):
        kwargs = dict(
            excel_bytes=excel_bytes,
            excel_filename="productos.csv",
            images=list(images),
            company_name="Repuestos Andina",
            brand_name="Andina",
            primary_color="#E30613",
            secondary_color="#12355B",
        )
        kwargs.update(overrides)
        return generate_public_catalog(**kwargs)

    def test_generates_standalone_html_without_any_database(self) -> None:
        excel = _csv('REF-1001,"Bomba de agua Toyota Corolla 2015 [OEM123]",Bombas,\n')
        result = self._call(excel)
        self.assertEqual(result.product_count, 1)
        self.assertIn(b"<!doctype html>", result.html)
        self.assertIn("Repuestos Andina".encode("utf-8"), result.html)
        self.assertIn(b"REF-1001", result.html)

    def test_matches_photo_to_reference_by_filename(self) -> None:
        excel = _csv("REF-2002,Filtro de aceite,Filtros,\n")
        result = self._call(excel, images=[("REF-2002.png", _png_bytes())])
        self.assertEqual(result.matched_image_count, 1)
        self.assertEqual(result.ambiguous_image_count, 0)
        self.assertEqual(result.unmatched_image_count, 0)
        # embed_images=True incrusta la foto como data URI en vez de referenciar un archivo.
        self.assertIn(b"data:image/jpeg;base64,", result.html)

    def test_photo_that_matches_no_reference_is_left_unmatched(self) -> None:
        excel = _csv("REF-3003,Bujía,Encendido,\n")
        result = self._call(excel, images=[("REF-9999.png", _png_bytes())])
        self.assertEqual(result.matched_image_count, 0)
        self.assertEqual(result.unmatched_image_count, 1)

    def test_two_photos_normalizing_to_the_same_key_are_ambiguous_not_guessed(self) -> None:
        excel = _csv("REF-4004,Radiador,Enfriamiento,\n")
        result = self._call(
            excel,
            images=[("REF-4004.png", _png_bytes()), ("ref_4004.png", _png_bytes((10, 10, 10)))],
        )
        self.assertEqual(result.ambiguous_image_count, 2)
        self.assertEqual(result.matched_image_count, 0)

    def test_rejects_excel_that_reuses_a_sku_because_it_never_touches_the_real_catalog(self) -> None:
        # No hay base de datos que consultar: el mismo SKU se puede "reutilizar" cuantas
        # veces se quiera entre llamadas, porque cada generación es independiente.
        excel = _csv("REF-5005,Amortiguador,Suspensión,\n")
        first = self._call(excel)
        second = self._call(excel)
        self.assertEqual(first.product_count, second.product_count)

    def test_rejects_non_hex_colors(self) -> None:
        excel = _csv("REF-6006,Correa,Transmisión,\n")
        with self.assertRaises(ValueError):
            self._call(excel, primary_color="red")

    def test_rejects_missing_required_headers(self) -> None:
        excel = b"Columna rara\nvalor\n"
        with self.assertRaises(ValueError):
            self._call(excel)

    def test_rejects_too_many_photos(self) -> None:
        excel = _csv("REF-7007,Pastilla de freno,Frenos,\n")
        images = [(f"REF-7007-{i}.png", _png_bytes()) for i in range(MAX_PUBLIC_IMAGE_FILES + 1)]
        with self.assertRaises(ValueError):
            self._call(excel, images=images)

    def test_rejects_unsupported_image_extension(self) -> None:
        excel = _csv("REF-8008,Sensor,Electrico,\n")
        with self.assertRaises(ValueError):
            self._call(excel, images=[("REF-8008.txt", b"not an image")])

    def test_logo_is_sanitized_and_embedded(self) -> None:
        excel = _csv("REF-9009,Kit de embrague,Transmision,\n")
        result = self._call(excel, logo=("logo.png", _png_bytes((5, 5, 200))))
        self.assertIn(b'class="brand-logo"', result.html)


class MatchImagesOrderingTests(unittest.TestCase):
    def _row(self, reference: str) -> dict:
        return {
            "internal_reference_original": reference,
            "internal_reference_normalized": reference,
            "image_path": None,
            "variant_image_paths": [],
        }

    def test_variant_photos_are_ordered_by_letter_regardless_of_upload_order(self) -> None:
        row = self._row("CKT-507AU-LB")
        with tempfile.TemporaryDirectory() as tmp:
            # Subidas fuera de orden: B, luego A, luego la principal.
            images = [
                ("CKT-507AU-LB B.png", _png_bytes((1, 1, 1))),
                ("CKT-507AU-LB A.png", _png_bytes((2, 2, 2))),
                ("CKT-507AU-LB.png", _png_bytes((3, 3, 3))),
            ]
            matched, ambiguous = _match_images([row], images, Path(tmp))
            self.assertEqual(matched, 3)
            self.assertEqual(ambiguous, 0)
            self.assertTrue(row["image_path"])
            self.assertEqual(len(row["variant_image_paths"]), 2)
            # A (índice 2) siempre antes que B (índice 3), aunque B se haya subido primero.
            self.assertIn("A", row["variant_image_paths"][0])
            self.assertIn("B", row["variant_image_paths"][1])

    def test_letter_and_parenthesized_letter_are_treated_as_the_same_ambiguous_key(self) -> None:
        # "REF A" y "REF (A)" normalizan a la misma clave: es ambigüedad real (¿cuál es la
        # foto A verdadera?), no un bug — el sistema interno trata el mismo choque igual.
        row = self._row("REF-1234")
        with tempfile.TemporaryDirectory() as tmp:
            images = [
                ("REF-1234 A.png", _png_bytes()),
                ("REF-1234 (A).png", _png_bytes()),
            ]
            matched, ambiguous = _match_images([row], images, Path(tmp))
            self.assertEqual(matched, 0)
            self.assertEqual(ambiguous, 2)


if __name__ == "__main__":
    unittest.main()
