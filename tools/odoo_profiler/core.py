from __future__ import annotations

import csv
import hashlib
import json
import posixpath
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET


_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_CELL_REF = re.compile(r"([A-Z]+)(\d+)", re.IGNORECASE)
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}(?:[T ][0-9:.+-Z]+)?$")
_YEAR_RANGE = re.compile(r"\b\d{2}\s*/\s*(?:\d{2}|~)", re.IGNORECASE)
_LITER = re.compile(r"\b\d+(?:\.\d+)?\s*L\b", re.IGNORECASE)
_CYLINDER = re.compile(r"\b\d+\s*CIL\.?\b", re.IGNORECASE)
_SIDE = re.compile(r"\b(?:LH|RH|IZQ\.?|DER\.?)\b", re.IGNORECASE)
_THICKNESS = re.compile(r"\b(?:ESPESOR\s*)?\d+(?:\.\d+)?\s*MM\b", re.IGNORECASE)


@dataclass(frozen=True)
class SheetData:
    name: str
    rows: list[list[Any]]
    row_numbers: list[int]
    formula_count: int = 0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).strip()).upper()


def _header_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _excel_column_index(reference: str) -> int:
    match = _CELL_REF.fullmatch(reference)
    if not match:
        raise ValueError(f"Referencia de celda XLSX inválida: {reference!r}")
    index = 0
    for char in match.group(1).upper():
        index = index * 26 + ord(char) - 64
    return index - 1


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child(element: ET.Element, name: str) -> ET.Element | None:
    return next((node for node in element if _local_name(node.tag) == name), None)


def _text_nodes(element: ET.Element | None) -> str:
    if element is None:
        return ""
    return "".join(node.text or "" for node in element.iter() if _local_name(node.tag) == "t")


def _parse_number(text: str) -> int | float | str:
    if re.fullmatch(r"[-+]?\d+", text):
        try:
            return int(text)
        except ValueError:
            return text
    try:
        return float(text)
    except ValueError:
        return text


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> Any:
    cell_type = cell.attrib.get("t", "")
    value_node = _child(cell, "v")
    raw = value_node.text if value_node is not None and value_node.text is not None else ""

    if cell_type == "inlineStr":
        return _text_nodes(_child(cell, "is"))
    if cell_type == "s":
        try:
            return shared_strings[int(raw)]
        except (ValueError, IndexError):
            return raw
    if cell_type == "b":
        return raw == "1"
    if cell_type in {"str", "e", "d"}:
        return raw
    if raw == "":
        return None
    return _parse_number(raw)


def _read_xlsx(path: Path) -> list[SheetData]:
    try:
        archive = zipfile.ZipFile(path)
    except zipfile.BadZipFile as exc:
        raise ValueError(f"El archivo no es un XLSX válido: {path}") from exc

    with archive:
        names = set(archive.namelist())
        required = {"xl/workbook.xml", "xl/_rels/workbook.xml.rels"}
        missing = required - names
        if missing:
            raise ValueError(f"XLSX incompleto; faltan: {', '.join(sorted(missing))}")

        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in names:
            shared_root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
            shared_strings = [_text_nodes(item) for item in shared_root if _local_name(item.tag) == "si"]

        relationships_root = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
        relationships = {
            relation.attrib["Id"]: relation.attrib["Target"]
            for relation in relationships_root
            if "Id" in relation.attrib and "Target" in relation.attrib
        }
        workbook_root = ET.fromstring(archive.read("xl/workbook.xml"))
        sheets_node = next(
            (node for node in workbook_root.iter() if _local_name(node.tag) == "sheets"),
            None,
        )
        if sheets_node is None:
            return []

        result: list[SheetData] = []
        for sheet_node in sheets_node:
            relationship_id = sheet_node.attrib.get(f"{{{_REL_NS}}}id")
            target = relationships.get(relationship_id or "")
            if not target:
                continue
            member = target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))
            if member not in names:
                raise ValueError(f"La hoja {sheet_node.attrib.get('name')} apunta a {member}, que no existe")

            sheet_root = ET.fromstring(archive.read(member))
            sheet_data = next(
                (node for node in sheet_root.iter() if _local_name(node.tag) == "sheetData"),
                None,
            )
            rows: list[list[Any]] = []
            row_numbers: list[int] = []
            formula_count = 0
            max_columns = 0
            if sheet_data is not None:
                for ordinal, row_node in enumerate(sheet_data, start=1):
                    row_number = int(row_node.attrib.get("r", ordinal))
                    sparse: dict[int, Any] = {}
                    for cell in row_node:
                        if _local_name(cell.tag) != "c":
                            continue
                        reference = cell.attrib.get("r")
                        column_index = _excel_column_index(reference) if reference else len(sparse)
                        sparse[column_index] = _xlsx_cell_value(cell, shared_strings)
                        if _child(cell, "f") is not None:
                            formula_count += 1
                    width = max(sparse, default=-1) + 1
                    max_columns = max(max_columns, width)
                    rows.append([sparse.get(index) for index in range(width)])
                    row_numbers.append(row_number)
            rows = [row + [None] * (max_columns - len(row)) for row in rows]
            result.append(
                SheetData(
                    name=sheet_node.attrib.get("name", f"Sheet{len(result) + 1}"),
                    rows=rows,
                    row_numbers=row_numbers,
                    formula_count=formula_count,
                )
            )
        return result


def _read_csv(path: Path) -> list[SheetData]:
    try:
        text = path.read_text(encoding="utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = path.read_text(encoding="latin-1")
        encoding = "latin-1"

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    rows = [list(row) for row in csv.reader(text.splitlines(), dialect)]
    width = max((len(row) for row in rows), default=0)
    rows = [row + [None] * (width - len(row)) for row in rows]
    name = f"{path.stem} [{encoding}; delimitador={repr(dialect.delimiter)}]"
    return [SheetData(name=name, rows=rows, row_numbers=list(range(1, len(rows) + 1)))]


def _read_source(path: Path) -> list[SheetData]:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return _read_xlsx(path)
    if suffix in {".csv", ".tsv"}:
        return _read_csv(path)
    raise ValueError("Formato no admitido. Use .xlsx, .csv o .tsv")


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 of a source file without modifying it."""
    return _sha256(Path(path))


def read_tabular_source(path: str | Path) -> list[SheetData]:
    """Read XLSX/CSV data with the profiler's standard-library reader."""
    return _read_source(Path(path))


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _value_key(value: Any) -> str:
    return json.dumps(_json_value(value), ensure_ascii=False, sort_keys=True)


def _value_type(value: Any) -> str:
    if value is None or value == "":
        return "blank"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "decimal"
    if isinstance(value, (datetime, date)):
        return "date"
    if isinstance(value, str) and _ISO_DATE.fullmatch(value.strip()):
        return "date_text"
    return "text"


def _duplicate_groups(
    values: list[Any],
    row_numbers: list[int],
    *,
    normalized: bool,
    limit: int = 100,
) -> tuple[int, list[dict[str, Any]]]:
    grouped: dict[str, dict[str, Any]] = {}
    for value, row_number in zip(values, row_numbers):
        if value is None or value == "":
            continue
        key = _normalize(value) if normalized else _value_key(value)
        group = grouped.setdefault(key, {"key": key, "values": set(), "rows": []})
        group["values"].add(str(value))
        group["rows"].append(row_number)
    duplicates = [group for group in grouped.values() if len(group["rows"]) > 1]
    duplicates.sort(key=lambda group: (-len(group["rows"]), group["key"]))
    output = [
        {
            "key": group["key"],
            "values": sorted(group["values"]),
            "rows": group["rows"],
            "count": len(group["rows"]),
        }
        for group in duplicates[:limit]
    ]
    return len(duplicates), output


def _column_profile(header: str, values: list[Any], row_numbers: list[int]) -> dict[str, Any]:
    nonblank = [value for value in values if value is not None and value != ""]
    strings = [str(value) for value in nonblank]
    type_counts = Counter(_value_type(value) for value in values)
    exact_unique = len({_value_key(value) for value in nonblank})
    normalized_unique = len({_normalize(value) for value in nonblank})
    lengths = [len(value) for value in strings]
    exact_count, exact_groups = _duplicate_groups(values, row_numbers, normalized=False)
    normalized_count, normalized_groups = _duplicate_groups(values, row_numbers, normalized=True)
    longest = sorted(
        (
            {"row": row, "length": len(str(value)), "value": str(value)}
            for value, row in zip(values, row_numbers)
            if value is not None and value != ""
        ),
        key=lambda item: (-item["length"], item["row"]),
    )[:5]
    return {
        "header": header,
        "rows": len(values),
        "nonblank": len(nonblank),
        "blanks": len(values) - len(nonblank),
        "completeness_pct": round(100 * len(nonblank) / max(1, len(values)), 2),
        "type_counts": dict(sorted(type_counts.items())),
        "unique_exact": exact_unique,
        "unique_normalized": normalized_unique,
        "duplicate_groups_exact_count": exact_count,
        "duplicate_groups_exact": exact_groups,
        "duplicate_groups_normalized_count": normalized_count,
        "duplicate_groups_normalized": normalized_groups,
        "min_length": min(lengths) if lengths else None,
        "max_length": max(lengths) if lengths else None,
        "average_length": round(sum(lengths) / len(lengths), 2) if lengths else None,
        "leading_or_trailing_whitespace_rows": [
            row for value, row in zip(values, row_numbers) if isinstance(value, str) and value != value.strip()
        ],
        "repeated_whitespace_rows": [
            row for value, row in zip(values, row_numbers) if isinstance(value, str) and re.search(r"\s{2,}", value)
        ],
        "line_break_rows": [
            row for value, row in zip(values, row_numbers) if isinstance(value, str) and re.search(r"[\r\n]", value)
        ],
        "control_character_rows": [
            row
            for value, row in zip(values, row_numbers)
            if isinstance(value, str) and re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", value)
        ],
        "longest_values": longest,
    }


def _make_unique_headers(raw_headers: list[Any]) -> tuple[list[str], list[str]]:
    headers: list[str] = []
    warnings: list[str] = []
    counts: Counter[str] = Counter()
    for index, raw in enumerate(raw_headers, start=1):
        base = str(raw or "").strip() or f"column_{index}"
        counts[base] += 1
        header = base if counts[base] == 1 else f"{base}__{counts[base]}"
        if not str(raw or "").strip():
            warnings.append(f"La columna {index} no tiene encabezado; se nombró {header}.")
        elif counts[base] > 1:
            warnings.append(f"Encabezado repetido {base!r}; se nombró {header}.")
        headers.append(header)
    return headers, warnings


def _find_column(headers: list[str], aliases: set[str]) -> int | None:
    return next((index for index, header in enumerate(headers) if _header_key(header) in aliases), None)


def _domain_profile(headers: list[str], rows: list[list[Any]], row_numbers: list[int]) -> dict[str, Any]:
    name_index = _find_column(headers, {"nombre", "name", "nombre del producto", "product name"})
    reference_index = _find_column(
        headers,
        {"referencia interna", "internal reference", "default code", "codigo interno", "sku"},
    )
    result: dict[str, Any] = {
        "name_column": headers[name_index] if name_index is not None else None,
        "reference_column": headers[reference_index] if reference_index is not None else None,
    }
    if name_index is None:
        result["warning"] = "No se reconoció una columna de nombre."
        return result

    names = [str(row[name_index] or "") for row in rows]
    references = [str(row[reference_index] or "") for row in rows] if reference_index is not None else [""] * len(rows)
    duplicate_names: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for name, reference, row_number in zip(names, references, row_numbers):
        if name:
            duplicate_names[_normalize(name)].append(
                {"row": row_number, "name": name, "reference": reference or None}
            )
    duplicate_name_groups = [
        {"normalized_name": key, "records": records}
        for key, records in duplicate_names.items()
        if len(records) > 1
    ]
    duplicate_name_groups.sort(key=lambda group: group["normalized_name"])

    prefix = "EMPAQUE CABEZOTE/CAMARA "
    lead_tokens: Counter[str] = Counter()
    for name in names:
        normalized = _normalize(name)
        remainder = normalized[len(prefix) :] if normalized.startswith(prefix) else normalized
        lead_tokens[remainder.split(" ", 1)[0] if remainder else ""] += 1

    result.update(
        {
            "exact_product_prefix": prefix,
            "exact_product_prefix_count": sum(name.startswith(prefix) for name in names),
            "duplicate_name_groups_count": len(duplicate_name_groups),
            "duplicate_name_groups": duplicate_name_groups[:100],
            "names_with_parentheses": sum(bool(re.search(r"\([^)]*\)", name)) for name in names),
            "names_with_year_range": sum(bool(_YEAR_RANGE.search(name)) for name in names),
            "names_with_open_ended_year": sum("~" in name for name in names),
            "names_with_liters": sum(bool(_LITER.search(name)) for name in names),
            "names_with_cylinders": sum(bool(_CYLINDER.search(name)) for name in names),
            "names_with_side": sum(bool(_SIDE.search(name)) for name in names),
            "names_with_thickness": sum(bool(_THICKNESS.search(name)) for name in names),
            "leading_tokens": lead_tokens.most_common(30),
        }
    )

    if reference_index is not None:
        result["reference_patterns"] = {
            "numeric_only": sum(bool(re.fullmatch(r"\d+", reference)) for reference in references),
            "alphanumeric_without_separator": sum(
                bool(re.fullmatch(r"(?=.*[A-Z])(?=.*\d)[A-Z0-9]+", reference, re.IGNORECASE))
                for reference in references
            ),
            "contains_hyphen": sum("-" in reference for reference in references),
            "contains_slash": sum("/" in reference for reference in references),
            "contains_whitespace": sum(bool(re.search(r"\s", reference)) for reference in references),
            "starts_with_zero": sum(reference.startswith("0") for reference in references),
        }
    return result


def _sheet_profile(sheet: SheetData) -> dict[str, Any]:
    nonempty_indices = [
        index for index, row in enumerate(sheet.rows) if any(value is not None and value != "" for value in row)
    ]
    if not nonempty_indices:
        return {
            "name": sheet.name,
            "empty": True,
            "physical_rows": len(sheet.rows),
            "formula_count": sheet.formula_count,
        }

    header_index = nonempty_indices[0]
    width = max((len(row) for row in sheet.rows[header_index:]), default=0)
    raw_headers = sheet.rows[header_index] + [None] * (width - len(sheet.rows[header_index]))
    headers, warnings = _make_unique_headers(raw_headers)

    data_rows: list[list[Any]] = []
    data_row_numbers: list[int] = []
    blank_rows_skipped = 0
    for row, row_number in zip(sheet.rows[header_index + 1 :], sheet.row_numbers[header_index + 1 :]):
        padded = row + [None] * (width - len(row))
        if not any(value is not None and value != "" for value in padded):
            blank_rows_skipped += 1
            continue
        data_rows.append(padded)
        data_row_numbers.append(row_number)

    columns = [
        _column_profile(header, [row[index] for row in data_rows], data_row_numbers)
        for index, header in enumerate(headers)
    ]

    row_groups: dict[str, list[int]] = defaultdict(list)
    normalized_row_groups: dict[str, list[int]] = defaultdict(list)
    for row, row_number in zip(data_rows, data_row_numbers):
        row_groups[json.dumps([_json_value(value) for value in row], ensure_ascii=False)].append(row_number)
        normalized_row_groups[json.dumps([_normalize(value) for value in row], ensure_ascii=False)].append(row_number)
    exact_duplicate_rows = [rows for rows in row_groups.values() if len(rows) > 1]
    normalized_duplicate_rows = [rows for rows in normalized_row_groups.values() if len(rows) > 1]

    representative_indices = sorted(
        {0, len(data_rows) // 4, len(data_rows) // 2, (3 * len(data_rows)) // 4, len(data_rows) - 1}
    ) if data_rows else []
    representative_rows = [
        {
            "row": data_row_numbers[index],
            "values": {header: _json_value(data_rows[index][column]) for column, header in enumerate(headers)},
        }
        for index in representative_indices
    ]

    return {
        "name": sheet.name,
        "empty": False,
        "header_row": sheet.row_numbers[header_index],
        "physical_rows": len(sheet.rows),
        "data_rows": len(data_rows),
        "blank_rows_skipped": blank_rows_skipped,
        "columns_count": len(headers),
        "headers": headers,
        "formula_count": sheet.formula_count,
        "warnings": warnings,
        "columns": columns,
        "exact_duplicate_row_groups_count": len(exact_duplicate_rows),
        "exact_duplicate_row_groups": exact_duplicate_rows[:100],
        "normalized_duplicate_row_groups_count": len(normalized_duplicate_rows),
        "normalized_duplicate_row_groups": normalized_duplicate_rows[:100],
        "domain": _domain_profile(headers, data_rows, data_row_numbers),
        "representative_rows": representative_rows,
    }


def profile_file(source: str | Path) -> dict[str, Any]:
    path = Path(source).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo: {path}")

    initial_hash = _sha256(path)
    initial_stat = path.stat()
    sheets = _read_source(path)
    final_hash = _sha256(path)
    final_stat = path.stat()
    if initial_hash != final_hash or initial_stat.st_size != final_stat.st_size:
        raise RuntimeError("El archivo fuente cambió durante el análisis; se abortó el reporte.")

    return {
        "profiler_version": "0.1.0",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "read_only_verification": {
            "initial_sha256": initial_hash,
            "final_sha256": final_hash,
            "unchanged": initial_hash == final_hash,
        },
        "source": {
            "name": path.name,
            "path": str(path),
            "format": path.suffix.lower().lstrip("."),
            "size_bytes": initial_stat.st_size,
            "sha256": initial_hash,
        },
        "workbook": {
            "sheets_count": len(sheets),
            "sheets": [_sheet_profile(sheet) for sheet in sheets],
        },
    }


def _escape_markdown(value: Any, limit: int = 120) -> str:
    text = str(value if value is not None else "")
    text = text.replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return text if len(text) <= limit else f"{text[: limit - 1]}…"


def _markdown_report(profile: dict[str, Any]) -> str:
    source = profile["source"]
    workbook = profile["workbook"]
    lines = [
        f"# Perfil de Odoo: {source['name']}",
        "",
        f"- Profiler: v{profile['profiler_version']}",
        f"- Generado: {profile['generated_at']}",
        f"- SHA-256: `{source['sha256']}`",
        f"- Archivo sin cambios: **{'sí' if profile['read_only_verification']['unchanged'] else 'no'}**",
        f"- Hojas: **{workbook['sheets_count']}**",
        "",
    ]
    for sheet in workbook["sheets"]:
        lines.extend([f"## Hoja: {sheet['name']}", ""])
        if sheet.get("empty"):
            lines.extend(["Hoja vacía.", ""])
            continue
        lines.extend(
            [
                f"- Fila de encabezados: {sheet['header_row']}",
                f"- Filas de datos: {sheet['data_rows']}",
                f"- Columnas: {sheet['columns_count']}",
                f"- Fórmulas: {sheet['formula_count']}",
                f"- Filas duplicadas exactas: {sheet['exact_duplicate_row_groups_count']}",
                "",
                "### Columnas",
                "",
                "| Columna | Tipos | Nulos | Completitud | Únicos | Duplicados | Longitud |",
                "|---|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for column in sheet["columns"]:
            types = ", ".join(f"{key}: {value}" for key, value in column["type_counts"].items())
            length = f"{column['min_length']}–{column['max_length']} (prom. {column['average_length']})"
            lines.append(
                f"| {_escape_markdown(column['header'])} | {_escape_markdown(types)} | {column['blanks']} | "
                f"{column['completeness_pct']}% | {column['unique_exact']} | "
                f"{column['duplicate_groups_exact_count']} | {length} |"
            )

        domain = sheet.get("domain", {})
        lines.extend(["", "### Diagnóstico de productos", ""])
        if domain.get("warning"):
            lines.extend([domain["warning"], ""])
        else:
            lines.extend(
                [
                    f"- Columna de nombre: `{domain.get('name_column')}`",
                    f"- Columna de referencia: `{domain.get('reference_column')}`",
                    f"- Nombres duplicados: {domain.get('duplicate_name_groups_count', 0)} grupos",
                    f"- Nombres con rango de años: {domain.get('names_with_year_range', 0)}",
                    f"- Nombres con año abierto (`~`): {domain.get('names_with_open_ended_year', 0)}",
                    f"- Nombres con cilindrada: {domain.get('names_with_liters', 0)}",
                    f"- Nombres con lado/posición: {domain.get('names_with_side', 0)}",
                    f"- Nombres con espesor: {domain.get('names_with_thickness', 0)}",
                    "",
                ]
            )
            duplicates = domain.get("duplicate_name_groups", [])
            if duplicates:
                lines.extend(
                    [
                        "#### Nombres repetidos con sus referencias",
                        "",
                        "| Nombre normalizado | Filas | Referencias |",
                        "|---|---:|---|",
                    ]
                )
                for group in duplicates:
                    records = group["records"]
                    rows = ", ".join(str(record["row"]) for record in records)
                    references = ", ".join(str(record.get("reference") or "∅") for record in records)
                    lines.append(
                        f"| {_escape_markdown(group['normalized_name'], 100)} | {rows} | {_escape_markdown(references)} |"
                    )
                lines.append("")

        whitespace_issues: list[str] = []
        for column in sheet["columns"]:
            for label, key in (
                ("espacios al inicio/final", "leading_or_trailing_whitespace_rows"),
                ("espacios repetidos", "repeated_whitespace_rows"),
                ("saltos de línea", "line_break_rows"),
                ("caracteres de control", "control_character_rows"),
            ):
                rows = column[key]
                if rows:
                    whitespace_issues.append(
                        f"- `{column['header']}`: {label} en filas {', '.join(map(str, rows[:30]))}"
                    )
        lines.extend(["### Anomalías de texto", ""])
        lines.extend(whitespace_issues or ["No se encontraron anomalías básicas de espacios o caracteres."])
        lines.append("")

        lines.extend(
            [
                "### Ejemplos representativos",
                "",
                "| Fila | Valores |",
                "|---:|---|",
            ]
        )
        for row in sheet["representative_rows"]:
            values = "; ".join(f"{key}={value}" for key, value in row["values"].items())
            lines.append(f"| {row['row']} | {_escape_markdown(values, 220)} |")
        lines.append("")

    lines.extend(
        [
            "## Recomendaciones del importador",
            "",
            "1. Conservar cada fila y valor original en staging antes de transformar.",
            "2. Usar el ID estable de Odoo como identidad cuando esté disponible.",
            "3. Tratar referencias como texto y conservar puntuación y ceros iniciales.",
            "4. Permitir nombres duplicados; no fusionar productos por nombre.",
            "5. Guardar aplicaciones y referencias extraídas como candidatos con confianza y regla de origen.",
            "6. Ejecutar primero en modo de simulación y nunca eliminar productos automáticamente.",
            "",
        ]
    )
    return "\n".join(lines)


def write_reports(profile: dict[str, Any], output_dir: str | Path, output_format: str = "both") -> list[Path]:
    destination = Path(output_dir).expanduser().resolve()
    destination.mkdir(parents=True, exist_ok=True)
    stem = Path(profile["source"]["name"]).stem
    fingerprint = profile["source"]["sha256"][:8]
    base = f"{stem}_profile_{fingerprint}"
    outputs: list[Path] = []
    if output_format in {"both", "json"}:
        json_path = destination / f"{base}.json"
        json_path.write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        outputs.append(json_path)
    if output_format in {"both", "markdown"}:
        markdown_path = destination / f"{base}.md"
        markdown_path.write_text(_markdown_report(profile), encoding="utf-8")
        outputs.append(markdown_path)
    return outputs
