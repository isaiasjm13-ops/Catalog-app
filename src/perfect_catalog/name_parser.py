from __future__ import annotations

import re
from typing import Any, Iterable


PARSER_VERSION = "vehicle-name-suggestions-v2"
REVIEW_STATUS = "pending_review"
SOURCE_PROFILES = frozenset({"generic", "perfect", "pdm"})

_BRANDS = {
    "TOY.": "Toyota", "TOYO.": "Toyota", "TOYOTA": "Toyota",
    "NIS.": "Nissan", "NISS.": "Nissan", "NISSAN": "Nissan",
    "MIT.": "Mitsubishi", "MITS.": "Mitsubishi", "MITSUBISHI": "Mitsubishi",
    "HON.": "Honda", "HONDA": "Honda", "HYU.": "Hyundai", "HYUNDAI": "Hyundai",
    "CHEV.": "Chevrolet", "CHEVROLET": "Chevrolet", "GM": "Chevrolet",
    "FORD": "Ford", "MAZDA": "Mazda", "KIA": "Kia", "VW": "Volkswagen",
    "VOLKSWAGEN": "Volkswagen", "SUZUKI": "Suzuki", "RENAULT": "Renault",
    "ISUZU": "Isuzu", "DAIHATSU": "Daihatsu", "SUBARU": "Subaru",
    "DODGE": "Dodge", "JEEP": "Jeep", "HINO": "Hino", "BMW": "BMW",
    "MERCEDES": "Mercedes-Benz", "M.BENZ": "Mercedes-Benz",
    "CHERY": "Chery", "GEELY": "Geely", "GREAT WALL": "Great Wall",
}
_BRAND_RE = re.compile(
    r"(?<![A-Z0-9])(" + "|".join(re.escape(k) for k in sorted(_BRANDS, key=len, reverse=True)) + r")(?![A-Z0-9])",
    re.IGNORECASE,
)
_YEAR_RE = re.compile(r"\b((?:19|20)\d{2})(?:\s*[-/]\s*((?:19|20)\d{2}))?\+?\b")
_SHORT_YEAR_RE = re.compile(r"(?<!\d)(\d{2})\s*[/\-]\s*(\d{2}|~|-)(?!\d)")
_DISPLACEMENT_RE = re.compile(r"\b(?:[0-9](?:[.,][0-9])?\s*L|[6-9]\d{2}\s*CC|[12]\d{3}\s*CC)\b", re.I)
_ENGINE_CODE_RE = re.compile(
    r"\b(?:[1-9][A-Z]{1,2}\d{1,2}(?:-[A-Z]{2,4})?|"
    r"[1-9][A-Z]{2}-[A-Z]{2,4}|[A-Z]{1,3}\d{2}[A-Z]{2,3})\b",
    re.I,
)
_POSITION_RE = re.compile(
    r"\b(DEL(?:ANTER[AO])?\.?|TRAS(?:ER[AO])?\.?|IZQ(?:UIERD[AO])?\.?|"
    r"DER(?:ECH[AO])?\.?|SUPERIOR|INFERIOR|FRONTAL|POSTERIOR)\b", re.I,
)
_POSITION_NAMES = {
    "DEL": "delantero", "DEL.": "delantero", "DELANTERA": "delantero", "DELANTERO": "delantero",
    "TRAS": "trasero", "TRAS.": "trasero", "TRASERA": "trasero", "TRASERO": "trasero",
    "IZQ": "izquierdo", "IZQ.": "izquierdo", "IZQUIERDA": "izquierdo", "IZQUIERDO": "izquierdo",
    "DER": "derecho", "DER.": "derecho", "DERECHA": "derecho", "DERECHO": "derecho",
    "FRONTAL": "delantero", "POSTERIOR": "trasero", "SUPERIOR": "superior", "INFERIOR": "inferior",
}
_BRACKET_RE = re.compile(r"\[([^]]+)]")
_EXPLICIT_OEM_RE = re.compile(r"\bOEM\s*[:#-]?\s*([A-Z0-9][A-Z0-9._/-]{2,60})", re.I)
_FMSI_RE = re.compile(r"(?<![A-Z0-9])D\d{3,5}(?:-\d{3,5})?(?![A-Z0-9])", re.I)
_REFERENCE_RE = re.compile(r"(?=.{3,50}$)(?=.*\d)\A[A-Z0-9][A-Z0-9._-]*\Z", re.I)
_COMPONENT_RE = re.compile(
    r"\b(?:KIT|JUEGO|EMPAQUE|EMPACADURA|SELLO|RETEN|RETÉN|ANILLO|BUJE|SOPORTE|"
    r"PASTILLA|ZAPATA|DISCO|FILTRO|BOMBA|CORREA|CADENA|TENSOR|ANTIRUIDO|RIN#?\d+)\b", re.I,
)


def _year(two_digits: str) -> int:
    value = int(two_digits)
    return 1900 + value if value >= 60 else 2000 + value


def _valid_years(year_from: int, year_to: int | None) -> dict[str, int | None] | None:
    if not 1950 <= year_from <= 2100:
        return None
    if year_to is not None and (year_to < year_from or year_to - year_from > 50):
        return None
    return {"from": year_from, "to": year_to}


def _unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = str(value or "").strip().upper()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            result.append(cleaned)
    return result


def _reference_parts(value: str) -> list[str]:
    return _unique(part for part in re.split(r"[,;|/\n\r]+", str(value or "")) if part.strip())


def _engine_suggestions(raw: str) -> list[dict[str, Any]]:
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for match in _DISPLACEMENT_RE.finditer(raw):
        evidence = match.group(0).upper().replace(",", ".").replace(" ", "")
        if evidence in seen:
            continue
        seen.add(evidence)
        liters = float(evidence[:-1]) if evidence.endswith("L") else int(evidence[:-2]) / 1000
        suggestions.append({"evidence": evidence, "kind": "displacement", "displacement_liters": liters, "confidence": 0.92})
    for match in _ENGINE_CODE_RE.finditer(raw):
        evidence = match.group(0).upper()
        if evidence in seen or _FMSI_RE.fullmatch(evidence):
            continue
        seen.add(evidence)
        suggestions.append({"evidence": evidence, "kind": "engine_code", "engine_code": evidence, "confidence": 0.68})
    return suggestions


def parse_product_name(
    raw_name: str,
    *, source_profile: str = "generic",
    additional_references: str | Iterable[str] = (),
) -> dict[str, Any]:
    """Create reviewable suggestions; never assert or publish inferred compatibility."""
    profile = str(source_profile or "generic").strip().lower()
    if profile not in SOURCE_PROFILES:
        raise ValueError(f"Perfil de parser desconocido: {source_profile!r}.")
    raw = str(raw_name or "").strip()
    brands: list[str] = []
    for match in _BRAND_RE.finditer(raw):
        brand = _BRANDS[match.group(1).upper()]
        if brand not in brands:
            brands.append(brand)

    years: dict[str, int | None] | None = None
    year_evidence: str | None = None
    match = _YEAR_RE.search(raw)
    if match:
        years = _valid_years(int(match.group(1)), int(match.group(2)) if match.group(2) else None)
        year_evidence = match.group(0) if years else None
    else:
        match = _SHORT_YEAR_RE.search(raw)
        if match:
            start = _year(match.group(1))
            end = None if match.group(2) in {"~", "-"} else _year(match.group(2))
            years = _valid_years(start, end)
            year_evidence = match.group(0) if years else None

    engine_suggestions = _engine_suggestions(raw)
    engines = [item["evidence"] for item in engine_suggestions]
    positions = _unique(_POSITION_NAMES[match.group(0).upper()] for match in _POSITION_RE.finditer(raw))
    fmsi_references = _unique(match.group(0) for match in _FMSI_RE.finditer(raw))
    explicit_oem = _unique(match.group(1) for match in _EXPLICIT_OEM_RE.finditer(raw))
    additional = _reference_parts(additional_references) if isinstance(additional_references, str) else _unique(additional_references)
    reference_suggestions = [
        {"value": value, "kind": "additional", "confidence": 1.0, "source": "dedicated_column"}
        for value in additional
    ]
    bracket_candidates: list[str] = []
    for contents in _BRACKET_RE.findall(raw):
        bracket_candidates.extend(value for value in _reference_parts(contents) if _REFERENCE_RE.fullmatch(value))
    bracket_candidates = _unique(bracket_candidates)
    for value in bracket_candidates:
        kind = "fmsi" if _FMSI_RE.fullmatch(value) else "bracket_reference"
        reference_suggestions.append({
            "value": value, "kind": kind, "confidence": 0.82 if kind == "fmsi" else 0.62,
            "source": "product_name",
        })
    oem_references = _unique(explicit_oem)
    if profile != "pdm":
        oem_references = _unique([*oem_references, *(value for value in bracket_candidates if value not in fmsi_references)])

    applications: list[dict[str, Any]] = []
    if brands:
        model_text = _BRAND_RE.sub(" ", raw)
        for pattern in (_YEAR_RE, _SHORT_YEAR_RE, _DISPLACEMENT_RE, _ENGINE_CODE_RE, _POSITION_RE, _BRACKET_RE, _FMSI_RE, _COMPONENT_RE):
            model_text = pattern.sub(" ", model_text)
        model = re.sub(r"\s+", " ", model_text).strip(" ()/,-.") or None
        reliable_engine = any(item["confidence"] >= 0.8 for item in engine_suggestions)
        confidence = min(0.95, 0.42 + (0.18 if model else 0) + (0.15 if years else 0) + (0.13 if reliable_engine else 0))
        applications = [{
            "vehicle_brand": brand, "model_suggestion": model, "years": years,
            "year_evidence": year_evidence, "engines": engines, "positions": positions,
            "confidence": round(confidence, 2), "review_status": REVIEW_STATUS,
        } for brand in brands]

    warnings = []
    if bracket_candidates and profile == "pdm":
        warnings.append("Los corchetes PDM se conservan como referencias candidatas; no se afirman como OEM.")
    if applications and any(item["model_suggestion"] is None for item in applications):
        warnings.append("Se detectó marca sin un modelo separable.")
    return {
        "source_name": raw, "source_profile": profile, "parser_version": PARSER_VERSION,
        "review_status": REVIEW_STATUS, "applications": applications,
        "engine_suggestions": engine_suggestions, "oem_references": oem_references,
        "fmsi_references": fmsi_references, "additional_references": additional,
        "reference_suggestions": reference_suggestions, "positions": positions,
        "warnings": warnings,
    }
