import unittest

from perfect_catalog.name_parser import PARSER_VERSION, parse_product_name


class NameParserTests(unittest.TestCase):
    def test_vehicle_data_is_only_a_pending_review_suggestion(self) -> None:
        result = parse_product_name("EMPAQUE TOY. COROLLA 1.8L 2010-2015 DEL. [11213-0T020]")
        self.assertEqual(result["parser_version"], PARSER_VERSION)
        self.assertEqual(result["review_status"], "pending_review")
        self.assertEqual(result["applications"][0]["vehicle_brand"], "Toyota")
        self.assertEqual(result["applications"][0]["years"], {"from": 2010, "to": 2015})
        self.assertIn("1.8L", result["applications"][0]["engines"])
        self.assertEqual(result["oem_references"], ["11213-0T020"])

    def test_empty_or_unrecognized_name_never_invents_an_application(self) -> None:
        self.assertEqual(parse_product_name("")["applications"], [])
        self.assertEqual(parse_product_name("EMPAQUE UNIVERSAL")["applications"], [])

