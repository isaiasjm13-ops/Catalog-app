import unittest

from perfect_catalog.tabular_detection import detect_columns, profile_text_table


class TabularDetectionTests(unittest.TestCase):
    def test_alias_detection_does_not_change_original_headers(self) -> None:
        headers = ["SKU", "Descripción", "Campo nuevo"]
        self.assertEqual(detect_columns(headers), {"name": "Descripción", "internal_reference": "SKU"})

    def test_pdm_additional_reference_column_is_detected_without_quantity_mapping(self) -> None:
        result = detect_columns(("Nombre", "Referencia interna", "Referencias Adicionales", "Cantidad a mano"))
        self.assertEqual(result["additional_references"], "Referencias Adicionales")
        self.assertNotIn("quantity_available", result)

    def test_cp1252_and_semicolon_are_profiled(self) -> None:
        profile = profile_text_table("CÓDIGO;DESCRIPCIÓN\nA-1;Empaque\n".encode("cp1252"))
        self.assertEqual(profile.encoding, "cp1252")
        self.assertEqual(profile.delimiter, ";")
        self.assertEqual(profile.suggestions["internal_reference"], "CÓDIGO")
        self.assertEqual(profile.suggestions["name"], "DESCRIPCIÓN")
