from __future__ import annotations

import re
from typing import Any


PARSER_VERSION = "vehicle-name-suggestions-v1"
REVIEW_STATUS = "pending_review"

_BRANDS = {
    "TOY.": "Toyota", "TOYO.": "Toyota", "TOYOTA": "Toyota",
    "NIS.": "Nissan", "NISS.": "Nissan", "NISSAN": "Nissan",
    "MIT.": "Mitsubishi", "MITS.": "Mitsubishi", "MITSUBISHI": "Mitsubishi",
    "HON.": "Honda", "HONDA": "Honda", "HYU.": "Hyundai", "HYUNDAI": "Hyundai",
    "CHEV.": "Chevrolet", "CHEVROLET": "Chevrolet", "FORD": "Ford",
    "MAZDA": "Mazda", "KIA": "Kia", "VW": "Volkswagen", "VOLKSWAGEN": "Volkswagen",
    "SUZUKI": "Suzuki", "RENAULT": "Renault", "ISUZU": "Isuzu",
}
_BRAND_RE = re.compile(
    r"(?<![A-Z0-9])(" + "|".join(re.escape(k) for k in sorted(_BRANDS, key=len, reverse=True)) + r")(?![A-Z0-9])",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})(?:\s*[-/]\s*((?:19|20)\d{2}))?\+?\b")
_SHORT_YEAR_RE = re.compile(r"\b(\d{2})\s*[/\-]\s*(\d{2}|~|-)\b")
_ENGINE_RE = re.compile(r"\b(?:\d+[.,]\d+\s*L|\d{3,4}\s*CC|[1-9][A-Z]{1,2}-?[A-Z0-9]{2,4})\b", re.I)
_POSITION_RE = re.compile(r"\b(DEL(?:ANTER[AO])?\.?|TRAS(?:ER[AO])?\.?|IZQ\.?|DER\.?|SUPERIOR|INFERIOR)\b", re.I)
_OEM_RE = re.compile(r"\[([^]]+)\]")


def _year(two_digits: str) -> int:
    value = int(two_digits)
    return 1900 + value if value >= 60 else 2000 + value


def parse_product_name(raw_name: str) -> dict[str, Any]:
    """Produce propuestas trazables; nunca constituye una decisión de publicación."""
    raw = str(raw_name or "").strip()
    brands = []
    for match in _BRAND_RE.finditer(raw):
        brand = _BRANDS[match.group(1).upper()]
        if brand not in brands:
            brands.append(brand)

    years: dict[str, int | None] | None = None
    match = _YEAR_RE.search(raw)
    if match:
        years = {"from": int(match.group(1)), "to": int(match.group(2)) if match.group(2) else None}
    else:
        match = _SHORT_YEAR_RE.search(raw)
        if match:
            years = {"from": _year(match.group(1)), "to": None if match.group(2) in {"~", "-"} else _year(match.group(2))}

    engines = list(dict.fromkeys(m.group(0).upper().replace(",", ".") for m in _ENGINE_RE.finditer(raw)))
    positions = list(dict.fromkeys(m.group(0).upper() for m in _POSITION_RE.finditer(raw)))
    oem_refs = []
    for contents in _OEM_RE.findall(raw):
        oem_refs.extend(part.strip().upper() for part in re.split(r"[,/]", contents) if part.strip())

    applications = []
    if brands:
        model_text = _BRAND_RE.sub(" ", raw)
        model_text = _YEAR_RE.sub(" ", model_text)
        model_text = _SHORT_YEAR_RE.sub(" ", model_text)
        model_text = _ENGINE_RE.sub(" ", model_text)
        model_text = _OEM_RE.sub(" ", model_text)
        model = re.sub(r"\s+", " ", model_text).strip(" /,-") or None
        applications = [{"vehicle_brand": brand, "model_suggestion": model, "years": years, "engines": engines} for brand in brands]

    return {
        "source_name": raw,
        "parser_version": PARSER_VERSION,
        "review_status": REVIEW_STATUS,
        "applications": applications,
        "oem_references": list(dict.fromkeys(oem_refs)),
        "positions": positions,
    }
