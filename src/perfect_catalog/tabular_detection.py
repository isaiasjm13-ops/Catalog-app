from __future__ import annotations

import csv
import io
import unicodedata
from dataclasses import dataclass
from typing import Iterable


ALIASES = {
    "name": ("nombre", "name", "producto", "descripcion", "descripción"),
    "internal_reference": ("referencia interna", "internal reference", "default code", "sku", "codigo", "código"),
    "category": ("categoria de producto", "categoría de producto", "category", "categoria"),
    "quantity_available": ("cantidad disponible", "available quantity", "qty available"),
}


def normalize_header(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return " ".join("".join(c for c in text if not unicodedata.combining(c)).lower().replace("_", " ").split())


def detect_columns(headers: Iterable[str]) -> dict[str, str]:
    actual = list(headers)
    indexed = {normalize_header(header): header for header in actual}
    result: dict[str, str] = {}
    for field, aliases in ALIASES.items():
        for alias in aliases:
            if normalize_header(alias) in indexed:
                result[field] = indexed[normalize_header(alias)]
                break
    return result


@dataclass(frozen=True)
class TextTableProfile:
    encoding: str
    delimiter: str
    headers: tuple[str, ...]
    suggestions: dict[str, str]


def profile_text_table(payload: bytes) -> TextTableProfile:
    """Detecta estructura solamente; el importador vigente conserva la autoridad contractual."""
    decoded = None
    encoding = ""
    for candidate in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            decoded = payload.decode(candidate)
            encoding = candidate
            break
        except UnicodeDecodeError:
            continue
    if decoded is None:
        raise ValueError("No se pudo decodificar el archivo como UTF-8 o Windows-1252.")
    sample = decoded[:65536]
    try:
        delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        delimiter = ","
    headers = tuple(next(csv.reader(io.StringIO(decoded), delimiter=delimiter), ()))
    if not headers:
        raise ValueError("El archivo no contiene encabezados.")
    return TextTableProfile(encoding, delimiter, headers, detect_columns(headers))
