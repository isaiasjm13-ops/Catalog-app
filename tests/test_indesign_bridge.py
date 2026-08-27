from pathlib import Path
import unittest


class InDesignBridgeTests(unittest.TestCase):
    def test_script_validates_snapshot_and_preserves_release_traceability(self) -> None:
        script = (
            Path(__file__).resolve().parents[1] / "indesign/ImportPerfectCatalog.jsx"
        ).read_text(encoding="utf-8")
        self.assertIn("perfect-catalog.indesign-snapshot.v1", script)
        self.assertIn('snapshot.release.status !== "published"', script)
        self.assertIn('insertLabel("perfect_catalog_release_id"', script)
        self.assertIn('insertLabel("perfect_catalog_snapshot_sha256"', script)
        self.assertIn("card.overflows", script)
        self.assertIn("SaveOptions.NO", script)
        for profile in ("T4", "T2", "T1", "TABLE"):
            self.assertIn(f'profile === "{profile}"' if profile != "T4" else 'return {perPage: 4', script)
        self.assertIn("separatorPage(document, group, theme)", script)
        self.assertIn("perfect-catalog.indesign-preflight.v1", script)
        self.assertIn("missing_images", script)
        self.assertIn("overflow_product_indexes", script)
        self.assertIn("unavailable_fonts", script)
        self.assertIn("imageBox.place(image)", script)
        self.assertIn('scriptFile.parent.fsName + "/catalog.indesign.json"', script)
        self.assertIn("adjacent.exists ? adjacent : File.openDialog", script)
        for theme in ("forest", "industrial", "midnight", "classic"):
            self.assertIn(f"{theme}:", script)
        self.assertIn('insertLabel("perfect_catalog_theme"', script)
        self.assertIn("themeDefinition(document, themeName, visual)", script)
        self.assertIn("visual.secondary_color", script)
        self.assertIn("fillColor: theme.secondary", script)
        self.assertIn("fillColor: theme.paper", script)
        self.assertIn("strokeColor = theme.primary", script)
        self.assertIn("group_count", script)
        self.assertIn("page_count", script)
        self.assertIn('value(product, "brand", "Sin marca")', script)
        self.assertIn('value(product, "oem_references", "No indicadas")', script)
        self.assertIn("configureDocument(document)", script)
        self.assertIn('pageWidth = "210mm"', script)
        self.assertIn('pageHeight = "297mm"', script)
        self.assertIn("documentBleedUniformSize = true", script)
        self.assertIn('documentBleedTopOffset = "3mm"', script)
        self.assertIn("MeasurementUnits.POINTS", script)
        self.assertIn('insertLabel("perfect_catalog_page_format", "A4-portrait")', script)
        self.assertIn('visual.title_font_family', script)
        self.assertIn('visual.body_font_family', script)
        self.assertIn('fontByName(titleFamily, "Bold")', script)
        self.assertIn('fontByName(bodyFamily, "Regular")', script)
        self.assertIn('box.texts[0].appliedFont = selectedFont', script)
        self.assertIn("function vehicleMakeMark", script)
        self.assertIn('groupBy === "vehicle_make"', script)
        self.assertIn("visual.vehicle_makes", script)


if __name__ == "__main__":
    unittest.main()
