from __future__ import annotations

import hashlib
import json
import unicodedata
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


def json_compatible(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, dict):
        return {
            _canonical_key(key): json_compatible(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [json_compatible(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    raise TypeError(f"Unsupported value for canonical JSON: {type(value).__name__}")


def _canonical_key(value: Any) -> str | int | float | bool | None:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (UUID, datetime, date, time, Decimal)):
        return json_compatible(value)
    raise TypeError(f"Unsupported dictionary key for canonical JSON: {type(value).__name__}")


def canonical_json(value: Any) -> str:
    return json.dumps(
        json_compatible(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def normalize_reference(value: Any) -> str:
    """Normalize conservatively while preserving punctuation and inner spacing."""
    return unicodedata.normalize("NFKC", str(value or "")).strip().upper()


def normalize_name(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).strip().upper().split())
