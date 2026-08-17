from __future__ import annotations

import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from tools.odoo_profiler import profile_file, write_reports


def _write_minimal_xlsx(path: Path) -> None:
    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
  <Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>"""
    root_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>"""
    workbook = """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets><sheet name="Productos" sheetId="1" r:id="rId1"/></sheets>
</workbook>"""
    workbook_rels = """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>"""
    sheet = """<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>
  <row r="1"><c r="A1" t="inlineStr"><is><t>Nombre</t></is></c><c r="B1" t="inlineStr"><is><t>Referencia interna</t></is></c></row>
  <row r="2"><c r="A2" t="inlineStr"><is><t>PIEZA TOY. 1.0L 19/~</t></is></c><c r="B2" t="inlineStr"><is><t>001-A</t></is></c></row>
  <row r="3"><c r="A3" t="inlineStr"><is><t>PIEZA TOY. 1.0L 19/~</t></is></c><c r="B3" t="inlineStr"><is><t>002-B</t></is></c></row>
</sheetData></worksheet>"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("[Content_Types].xml", content_types)
        archive.writestr("_rels/.rels", root_rels)
        archive.writestr("xl/workbook.xml", workbook)
        archive.writestr("xl/_rels/workbook.xml.rels", workbook_rels)
        archive.writestr("xl/worksheets/sheet1.xml", sheet)


class ProfilerTests(unittest.TestCase):
    def test_profiles_csv_and_preserves_source(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "productos.csv"
            source.write_text(
                "Nombre;Referencia interna\nPieza A;ABC-1\nPieza A;ABC-2\nPieza B;\n",
                encoding="utf-8",
            )
            original = source.read_bytes()
            profile = profile_file(source)
            sheet = profile["workbook"]["sheets"][0]
            self.assertEqual(sheet["data_rows"], 3)
            self.assertEqual(sheet["columns"][1]["blanks"], 1)
            self.assertEqual(sheet["domain"]["duplicate_name_groups_count"], 1)
            self.assertTrue(profile["read_only_verification"]["unchanged"])
            self.assertEqual(source.read_bytes(), original)

    def test_profiles_minimal_xlsx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "productos.xlsx"
            _write_minimal_xlsx(source)
            profile = profile_file(source)
            sheet = profile["workbook"]["sheets"][0]
            self.assertEqual(sheet["name"], "Productos")
            self.assertEqual(sheet["headers"], ["Nombre", "Referencia interna"])
            self.assertEqual(sheet["data_rows"], 2)
            self.assertEqual(sheet["columns"][1]["unique_exact"], 2)
            self.assertEqual(sheet["domain"]["duplicate_name_groups_count"], 1)

    def test_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "productos.csv"
            source.write_text("Nombre,Referencia interna\nPieza,ABC-1\n", encoding="utf-8")
            profile = profile_file(source)
            outputs = write_reports(profile, root / "reports")
            self.assertEqual({path.suffix for path in outputs}, {".json", ".md"})
            loaded = json.loads(next(path for path in outputs if path.suffix == ".json").read_text(encoding="utf-8"))
            self.assertEqual(loaded["source"]["name"], "productos.csv")


if __name__ == "__main__":
    unittest.main()
