import unittest

from perfect_catalog.name_parser import PARSER_VERSION, parse_product_name
from perfect_catalog.vehicle_makes import VEHICLE_MAKES, VEHICLE_MAKE_ALIASES


class NameParserTests(unittest.TestCase):
    def test_curated_registry_contract_is_stable_and_deduplicated(self) -> None:
        self.assertEqual(len(VEHICLE_MAKES), 100)
        self.assertEqual(len(VEHICLE_MAKE_ALIASES), 122)
        self.assertEqual(len(VEHICLE_MAKES), len(set(VEHICLE_MAKES)))

    def test_global_registry_recognizes_current_aliases_without_publishing_them(self) -> None:
        cases = {
            "CHIREY TIGGO 7 2022-2025 1.5L": "Chery",
            "GWM POER 2021-2024 2.0L": "Great Wall",
            "MERCEDES-BENZ SPRINTER 2019-2024 2.1L": "Mercedes-Benz",
            "SSANG YONG KORANDO 2014-2018 2.0L": "KGM",
            "VW AMAROK 2011-2020 2.0L": "Volkswagen",
            "CITROËN C3 2018-2023 1.2L": "Citroën",
            "MARUTI SUZUKI SWIFT 2017-2024 1.2L": "Maruti Suzuki",
        }
        for source, expected in cases.items():
            with self.subTest(source=source):
                parsed = parse_product_name(source)
                self.assertEqual(parsed["applications"][0]["vehicle_brand"], expected)
                self.assertEqual(parsed["review_status"], "pending_review")

    def test_ambiguous_generic_abbreviations_are_not_claimed_as_vehicle_makes(self) -> None:
        parsed = parse_product_name("KIT GM RAM MINI SEAT MAN 2018-2020")
        self.assertEqual(parsed["applications"], [])

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

    def test_pdm_brackets_remain_candidates_without_inventing_oem(self) -> None:
        result = parse_product_name(
            "PASTILLA CHEV. AVEO 04-10 DEL. [D1035-7779/96800089]",
            source_profile="pdm",
        )
        self.assertEqual(result["source_profile"], "pdm")
        self.assertEqual(result["positions"], ["DELANTERO"])
        self.assertEqual(result["fmsi_references"], ["D1035-7779"])
        self.assertEqual(result["oem_references"], [])
        self.assertEqual(
            [item["value"] for item in result["reference_suggestions"]],
            ["D1035-7779", "96800089"],
        )
        self.assertTrue(result["warnings"])

    def test_dedicated_additional_references_are_exact_high_confidence_evidence(self) -> None:
        result = parse_product_name(
            "FILTRO UNIVERSAL",
            source_profile="pdm",
            additional_references=" abc-01 ; ABC-01 | zz99 ",
        )
        self.assertEqual(result["additional_references"], ["ABC-01", "ZZ99"])
        self.assertEqual(result["reference_suggestions"][0], {
            "value": "ABC-01", "kind": "additional", "confidence": 1.0,
            "source": "dedicated_column",
        })

    def test_engine_and_application_suggestions_include_confidence_and_structure(self) -> None:
        result = parse_product_name("EMPAQUE TOYOTA COROLLA 1800CC 1ZZ-FE 2012-2018 TRASERO")
        app = result["applications"][0]
        self.assertEqual(app["model_suggestion"], "COROLLA")
        self.assertEqual(app["positions"], ["TRASERO"])
        self.assertGreater(app["confidence"], 0.8)
        self.assertEqual(result["engine_suggestions"][0]["displacement_liters"], 1.8)
        self.assertTrue(all(item["review_status"] == "pending_review" for item in result["applications"]))

    def test_unknown_source_profile_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "Perfil de parser desconocido"):
            parse_product_name("TOYOTA COROLLA", source_profile="inventado")
