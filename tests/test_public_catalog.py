from __future__ import annotations

import io
import unittest

from PIL import Image

from perfect_catalog.public_catalog import (
    MAX_PUBLIC_IMAGE_FILES,
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


if __name__ == "__main__":
    unittest.main()
